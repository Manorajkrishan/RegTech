"""Stripe subscription integration. Webhook, not checkout redirect, grants access."""
import asyncio
import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .database import BillingEvent, Organisation, User, get_db
from .security import current_user
from .team import require_owner

router = APIRouter(prefix="/api/billing", tags=["billing"])


def billing_mode() -> str | None:
    """Fail-closed boundary: never use live Stripe keys outside an explicitly enabled production account."""
    if not (
        settings.stripe_webhook_secret.startswith("whsec_")
        and settings.stripe_price_id.startswith("price_")
    ):
        return None
    if settings.environment in ("development", "staging") and settings.stripe_secret_key.startswith("sk_test_"):
        return "test"
    if (
        settings.environment == "production"
        and settings.stripe_live_billing_enabled
        and settings.stripe_secret_key.startswith("sk_live_")
    ):
        return "live"
    return None


def configured() -> bool:
    return billing_mode() is not None


async def verified_price():
    """Stripe itself must confirm the configured recurring price and billing environment."""
    mode = billing_mode()
    if mode is None:
        raise HTTPException(503, "Billing is not configured for this environment")
    stripe.api_key = settings.stripe_secret_key
    try:
        price = await stripe_call(stripe.Price.retrieve, settings.stripe_price_id)
    except stripe.StripeError as exc:
        raise HTTPException(502, "Unable to verify current subscription price") from exc
    recurrence = price.get("recurring") or {}
    if not (
        price.get("id") == settings.stripe_price_id
        and price.get("active") is True
        and price.get("livemode") is (mode == "live")
        and price.get("type") == "recurring"
        and recurrence.get("interval") in ("month", "year")
        and price.get("currency") == settings.stripe_expected_currency.lower()
        and isinstance(price.get("unit_amount"), int)
        and price["unit_amount"] > 0
    ):
        raise HTTPException(503, "Configured price failed verification (mode, currency, recurring or active)")
    return price


async def stripe_call(fn, **kwargs):
    return await asyncio.to_thread(fn, **kwargs)


@router.get("/status")
async def status(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    org = await db.get(Organisation, user.org_id)
    paid = org.subscription_status in ("active", "trialing")
    return {
        "plan": "pro" if paid else "free",
        "subscription_status": org.subscription_status,
        "checkout_available": configured(),
        "billing_mode": billing_mode() or "disabled",
        "free_activity_limit": settings.free_activity_limit,
        "free_team_limit": 3,
        "can_manage_billing": user.role == "owner"
    }


@router.get("/offer")
async def offer(
    user: User = Depends(current_user)
):
    """Offer price comes from Stripe; never guess it in the frontend."""
    price = await verified_price()
    return {
        "currency": price["currency"], "unit_amount": price["unit_amount"],
        "interval": price["recurring"]["interval"]
    }


@router.post("/checkout")
async def checkout(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    require_owner(user)
    if not configured():
        raise HTTPException(503, "Billing not configured. No payment was attempted.")
    org = await db.get(Organisation, user.org_id)
    if org.subscription_status in ("active", "trialing"):
        raise HTTPException(409, "Subscription already active; open billing portal")
    await verified_price()
    stripe.api_key = settings.stripe_secret_key
    try:
        if not org.stripe_customer_id:
            customer = await stripe_call(
                stripe.Customer.create,
                email=user.email, name=org.name, metadata={"org_id": org.id},
                idempotency_key="customer-" + org.id
            )
            org.stripe_customer_id = customer.id
            await db.commit()
        session = await stripe_call(
            stripe.checkout.Session.create,
            mode="subscription", customer=org.stripe_customer_id,
            client_reference_id=org.id,
            line_items=[{"price": settings.stripe_price_id, "quantity": 1}],
            allow_promotion_codes=True,
            success_url=settings.app_public_url.rstrip("/") + "/?billing=success",
            cancel_url=settings.app_public_url.rstrip("/") + "/?billing=cancel",
            metadata={"org_id": org.id}
        )
        return {"url": session.url}
    except stripe.StripeError as exc:
        raise HTTPException(502, "Payment provider currently unavailable") from exc


@router.post("/portal")
async def portal(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    require_owner(user)
    if not configured():
        raise HTTPException(503, "Billing not configured")
    org = await db.get(Organisation, user.org_id)
    if not org.stripe_customer_id:
        raise HTTPException(404, "No billing customer exists")
    stripe.api_key = settings.stripe_secret_key
    try:
        session = await stripe_call(
            stripe.billing_portal.Session.create,
            customer=org.stripe_customer_id,
            return_url=settings.app_public_url.rstrip("/")
        )
        return {"url": session.url}
    except stripe.StripeError as exc:
        raise HTTPException(502, "Payment provider currently unavailable") from exc


@router.post("/webhook")
async def webhook(request: Request, db: AsyncSession = Depends(get_db)):
    mode = billing_mode()
    if mode is None:
        raise HTTPException(503, "Billing webhook is not configured for this environment")
    data = await request.body()
    if len(data) > 262144:
        raise HTTPException(413, "Webhook too large")
    signature = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(
            data, signature, settings.stripe_webhook_secret
        )
    except (ValueError, stripe.SignatureVerificationError):
        raise HTTPException(400, "Invalid Stripe signature or payload")

    if event.get("livemode") is not (mode == "live"):
        raise HTTPException(400, "Stripe event mode does not match the configured account")

    if await db.get(BillingEvent, event["id"]):
        return {"received": True, "duplicate": True}

    etype = event["type"]
    if etype in ("customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted"):
        obj = event["data"]["object"]
        customer = obj.get("customer")
        org = await db.scalar(select(Organisation).where(
            Organisation.stripe_customer_id == customer
        ).with_for_update())
        if org is not None:
            timestamp = int(event.get("created", 0))
            subscription_id = obj.get("id")
            foreign_active_subscription = (
                org.subscription_id
                and org.subscription_id != subscription_id
                and org.subscription_status in ("active", "trialing")
            )
            state = obj.get("status", "inactive")
            # An equal-timestamp cancellation/downgrade wins against an upgrade:
            # Stripe event delivery can be out of order within the same second.
            should_update = (
                timestamp > org.subscription_event_created
                or (
                    timestamp == org.subscription_event_created
                    and state not in ("active", "trialing")
                )
            )
            if not foreign_active_subscription and subscription_id and should_update:
                prices = {
                    entry.get("price", {}).get("id")
                    for entry in obj.get("items", {}).get("data", [])
                }
                eligible = settings.stripe_price_id in prices
                # A signed update with unrelated price or unrecognized state does NOT unlock access.
                org.subscription_status = state if eligible and state in (
                    "active", "trialing"
                ) else "free"
                org.subscription_id = obj.get("id") if eligible else None
                org.subscription_price_id = settings.stripe_price_id if eligible else None
                org.subscription_event_created = timestamp

    db.add(BillingEvent(id=event["id"], event_type=etype))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return {"received": True, "duplicate": True}
    return {"received": True}

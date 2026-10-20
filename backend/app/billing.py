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


def configured() -> bool:
    return bool(
        settings.stripe_secret_key and settings.stripe_webhook_secret
        and settings.stripe_price_id
    )


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
        "free_activity_limit": settings.free_activity_limit,
        "free_team_limit": 3,
        "can_manage_billing": user.role == "owner"
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
    if not settings.stripe_webhook_secret:
        raise HTTPException(503, "Billing webhook is not configured")
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
            if timestamp >= org.subscription_event_created:
                prices = {
                    entry.get("price", {}).get("id")
                    for entry in obj.get("items", {}).get("data", [])
                }
                eligible = settings.stripe_price_id in prices
                state = obj.get("status", "inactive")
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

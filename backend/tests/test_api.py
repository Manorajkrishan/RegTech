"""Integration tests: authentication, tenant isolation, approval and report integrity."""
import os
import tempfile
from uuid import uuid4

# Configure DB before app import; no production credentials are involved.
os.environ["ENVIRONMENT"] = "development"
os.environ["DB_URL"] = "sqlite+aiosqlite:///" + tempfile.mktemp(prefix="regtech-test-", suffix=".sqlite3")

from fastapi.testclient import TestClient
from main import app


def identity():
    address = str(uuid4())[:12]
    return {"organisation": "Test " + address, "email": address + "@example.com",
            "password": "SafeLocalTestPassword#2026"}


def register(client, account):
    response = client.post("/api/auth/register", json=account)
    assert response.status_code == 201, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def activity():
    return {
        "description": "Purchased business electricity", "supplier": "Utility",
        "activity_date": "2026-01-31", "factor_id": "electricity",
        "quantity": 200, "unit": "kWh", "scope": "Scope 2",
        "evidence_reference": "Invoice A, page 1; reviewed meter reading"
    }


def test_register_and_tenant_isolation():
    with TestClient(app) as client:
        first = identity()
        second = identity()
        a = register(client, first)
        b = register(client, second)
        assert client.get("/api/activities").status_code == 401
        assert client.post("/api/auth/login", json={
            "email": first["email"], "password": "wrong"
        }).status_code == 401
        assert client.post("/api/auth/login", json={
            "email": first["email"], "password": first["password"]
        }).status_code == 200

        draft = client.post("/api/activities", headers=a, json=activity())
        assert draft.status_code == 201, draft.text
        record = draft.json()
        assert record["status"] == "draft"
        assert client.get("/api/reports/summary", headers=a).json()["approved_activity_count"] == 0

        assert client.get("/api/activities", headers=b).json() == []
        assert client.patch("/api/activities/" + record["id"] + "/approve", headers=b).status_code == 404

        approved = client.patch("/api/activities/" + record["id"] + "/approve", headers=a)
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"

        report_a = client.get("/api/reports/summary", headers=a).json()
        report_b = client.get("/api/reports/summary", headers=b).json()
        assert report_a["approved_activity_count"] == 1
        assert report_a["total_kg_co2e"] > 0
        assert report_b["total_kg_co2e"] == 0

        assert client.put("/api/activities/" + record["id"], headers=a, json=activity()).status_code == 409
        assert client.patch("/api/activities/" + record["id"] + "/void", headers=a).status_code == 200
        assert client.get("/api/reports/summary", headers=a).json()["approved_activity_count"] == 0
        assert len(client.get("/api/audit", headers=a).json()) == 3


def test_rejected_bad_inputs_and_fake_upload():
    with TestClient(app) as client:
        auth = register(client, identity())
        invalid = activity()
        invalid["unit"] = "GBP"
        assert client.post("/api/activities", headers=auth, json=invalid).status_code == 422
        assert client.post(
            "/api/invoices/extract", headers=auth,
            files={"file": ("fake.pdf", b"not-a-pdf", "application/pdf")}
        ).status_code == 415
        assert client.get("/api/factors", headers=auth).json()["factor_year"] == 2026


def test_activity_date_must_match_factor_year():
    with TestClient(app) as client:
        auth = register(client, identity())
        invalid = activity()
        invalid["activity_date"] = "2024-01-31"
        response = client.post("/api/activities", headers=auth, json=invalid)
        assert response.status_code == 422
        assert "factor vintage" in response.json()["detail"]



def test_logout_revokes_access_token_and_password_change():
    with TestClient(app) as client:
        account = identity()
        auth = register(client, account)
        assert client.get("/api/me", headers=auth).status_code == 200
        assert client.post("/api/auth/logout", headers=auth).status_code == 200
        assert client.get("/api/me", headers=auth).status_code == 401
        new = client.post("/api/auth/login", json={
            "email": account["email"], "password": account["password"]
        })
        assert new.status_code == 200
        current = {"Authorization": "Bearer " + new.json()["access_token"]}
        result = client.post("/api/auth/change-password", headers=current, json={
            "current_password": account["password"], "new_password": "ReplacedStrongPassword#2026"
        })
        assert result.status_code == 200, result.text
        assert client.get("/api/me", headers=current).status_code == 401
        assert client.post("/api/auth/login", json={
            "email": account["email"], "password": account["password"]
        }).status_code == 401
        assert client.post("/api/auth/login", json={
            "email": account["email"], "password": "ReplacedStrongPassword#2026"
        }).status_code == 200


def test_password_reset_one_time_and_no_account_enumeration(monkeypatch):
    from app import account_actions
    captured = []

    async def fake_mail(recipient, purpose, secret):
        captured.append((recipient, purpose, secret))

    monkeypatch.setattr(account_actions, "deliver_email", fake_mail)
    with TestClient(app) as client:
        account = identity()
        auth = register(client, account)
        missing = client.post(
            "/api/auth/request-password-reset",
            json={"email": "missing-account@example.com"}
        )
        found = client.post(
            "/api/auth/request-password-reset",
            json={"email": account["email"]}
        )
        assert found.status_code == missing.status_code == 202
        assert found.json() == missing.json()
        assert len(captured) == 1
        assert captured[0][1] == "reset_password"
        token = captured[0][2]
        assert client.post("/api/auth/reset-password", json={
            "token": token, "new_password": "A_New_Strong_Password_2026!"
        }).status_code == 200
        assert client.get("/api/me", headers=auth).status_code == 401
        assert client.post("/api/auth/reset-password", json={
            "token": token, "new_password": "Another_Strong_Password_2026!"
        }).status_code == 400
        assert client.post("/api/auth/login", json={
            "email": account["email"], "password": "A_New_Strong_Password_2026!"
        }).status_code == 200


def test_verification_token_is_single_use(monkeypatch):
    from app import account_actions
    captured = []

    async def fake_mail(recipient, purpose, secret):
        captured.append(secret)

    monkeypatch.setattr(account_actions, "deliver_email", fake_mail)
    with TestClient(app) as client:
        account = identity()
        auth = register(client, account)
        response = client.post(
            "/api/auth/resend-verification", json={"email": account["email"]}
        )
        assert response.status_code == 202
        assert len(captured) == 1
        token = captured[0]
        assert client.post("/api/auth/verify-email", json={"token": token}).status_code == 200
        assert client.post("/api/auth/verify-email", json={"token": token}).status_code == 400
        # Verification revokes tokens issued before the verification event.
        assert client.get("/api/me", headers=auth).status_code == 401


def test_login_throttling():
    from app.rate_limit import reset_for_tests, throttle
    from fastapi import HTTPException
    from types import SimpleNamespace
    reset_for_tests()
    request = SimpleNamespace(client=SimpleNamespace(host="isolated-test-peer"))
    for _ in range(15):
        throttle(request, "login")
    try:
        throttle(request, "login")
    except HTTPException as error:
        assert error.status_code == 429
        assert "Retry-After" in error.headers
    else:
        raise AssertionError("Exceeded login rate limit without a 429")


def test_login_lockout_after_repeated_failures():
    from app.rate_limit import reset_for_tests
    reset_for_tests()
    with TestClient(app) as client:
        account = identity()
        register(client, account)
        for _ in range(5):
            assert client.post("/api/auth/login", json={
                "email": account["email"], "password": "Incorrect-Password"
            }).status_code == 401
        assert client.post("/api/auth/login", json={
            "email": account["email"], "password": account["password"]
        }).status_code == 401



def test_team_workflow_and_role_permissions(monkeypatch):
    from app import team as team_module
    from app.rate_limit import reset_for_tests

    reset_for_tests()
    invitations = []

    async def deliver(email, organization, secret):
        invitations.append((email, secret))

    monkeypatch.setattr(team_module, "send_invite", deliver)
    with TestClient(app) as client:
        owner = register(client, identity())
        separate = register(client, identity())
        email = "team-" + str(uuid4())[:10] + "@example.com"
        invited = client.post("/api/team/invitations", headers=owner,
                              json={"email": email, "role": "editor"})
        assert invited.status_code == 201, invited.text
        accepted = client.post("/api/team/accept", json={
            "token": invitations[-1][1], "password": "InvitePasswordValid2026!"
        })
        assert accepted.status_code == 200, accepted.text
        editor = {"Authorization": "Bearer " + accepted.json()["access_token"]}
        assert client.post("/api/team/accept", json={
            "token": invitations[-1][1], "password": "InvitePasswordValid2026!"
        }).status_code == 400
        assert client.post("/api/team/invitations", headers=editor, json={
            "email": "cannot@example.com", "role": "viewer"
        }).status_code == 403
        draft = client.post("/api/activities", headers=editor, json=activity())
        assert draft.status_code == 201, draft.text
        activity_id = draft.json()["id"]
        assert client.patch("/api/activities/" + activity_id + "/approve",
                            headers=editor).status_code == 403
        assert client.patch("/api/activities/" + activity_id + "/approve",
                            headers=separate).status_code == 404
        roster = client.get("/api/team", headers=owner).json()
        member = next(m for m in roster["members"] if m["email"] == email)
        assert client.post("/api/team/members/" + member["id"] + "/deactivate",
                           headers=owner).status_code == 200
        assert client.get("/api/me", headers=editor).status_code == 401


def test_atomic_csv_import_and_free_quota(monkeypatch):
    from app.config import settings
    from app.rate_limit import reset_for_tests

    reset_for_tests()
    headers = "description,supplier,activity_date,factor_id,quantity,unit,scope,evidence_reference\n"
    valid = headers + (
        "January power,Utility,2026-01-20,electricity,100,kWh,Scope 2,invoice-Jan\n"
        "February power,Utility,2026-02-20,electricity,120,kWh,Scope 2,invoice-Feb\n"
    )
    with TestClient(app) as client:
        owner = register(client, identity())
        wrong = valid.replace("120,kWh", "120,GBP")
        response = client.post("/api/activities/import-csv", headers=owner,
                               files={"file": ("entries.csv", wrong.encode(), "text/csv")})
        assert response.status_code == 422
        assert client.get("/api/activities", headers=owner).json() == []
        good = client.post("/api/activities/import-csv", headers=owner,
                           files={"file": ("entries.csv", valid.encode(), "text/csv")})
        assert good.status_code == 201, good.text
        assert good.json()["created"] == 2
        assert all(row["status"] == "draft"
                   for row in client.get("/api/activities", headers=owner).json())
        monkeypatch.setattr(settings, "free_activity_limit", 2)
        assert client.post("/api/activities", headers=owner, json=activity()).status_code == 402
        row = client.get("/api/activities", headers=owner).json()[0]
        assert client.patch("/api/activities/" + row["id"] + "/approve",
                            headers=owner).status_code == 200
        assert client.get("/api/reports/summary?year=2026",
                          headers=owner).json()["approved_activity_count"] == 1
        assert client.get("/api/reports/summary?year=2025",
                          headers=owner).json()["approved_activity_count"] == 0



def test_billing_requires_config_and_signed_webhooks(monkeypatch):
    from app.config import settings
    with TestClient(app) as client:
        owner = register(client, identity())
        response = client.get("/api/billing/status", headers=owner)
        assert response.status_code == 200 and response.json()["plan"] == "free"
        assert client.post("/api/billing/checkout", headers=owner).status_code == 503
        assert client.post("/api/billing/webhook", content=b"{}").status_code == 503
        monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_unit_local")
        monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_unit_local")
        monkeypatch.setattr(settings, "stripe_price_id", "price_unit_local")
        assert client.post("/api/billing/webhook", content=b"{}",
                           headers={"stripe-signature": "invalid"}).status_code == 400


def test_stripe_event_is_idempotent_and_price_scoped(monkeypatch):
    from app import billing
    from app.config import settings
    from types import SimpleNamespace

    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_unit_local")
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_unit_local")
    monkeypatch.setattr(settings, "stripe_price_id", "price_for_unit_tests")
    async def provider(fn, *args, **kwargs):
        if fn == billing.stripe.Price.retrieve:
            return {"id": "price_for_unit_tests", "active": True, "livemode": False,
                    "type": "recurring", "recurring": {"interval": "month"},
                    "currency": "gbp", "unit_amount": 1900}
        if "email" in kwargs:
            return SimpleNamespace(id="cus_fixture")
        return SimpleNamespace(url="https://checkout.stripe.com/test-only")
    monkeypatch.setattr(billing, "stripe_call", provider)

    with TestClient(app) as client:
        owner = register(client, identity())
        offer = client.get("/api/billing/offer", headers=owner)
        assert offer.status_code == 200, offer.text
        assert offer.json() == {"currency": "gbp", "unit_amount": 1900, "interval": "month"}
        checkout = client.post("/api/billing/checkout", headers=owner)
        assert checkout.status_code == 200, checkout.text
        event = {
            "id": "evt_" + str(uuid4()),
            "type": "customer.subscription.updated",
            "created": 1000, "livemode": False,
            "data": {"object": {
                "id": "sub_test", "customer": "cus_fixture",
                "status": "active", "items": {"data": [{
                    "price": {"id": "price_for_unit_tests"}
                }]}
            }}
        }
        monkeypatch.setattr(billing.stripe.Webhook, "construct_event",
                            lambda body, sig, key: event)
        url = "/api/billing/webhook"
        first = client.post(url, content=b"{}", headers={"stripe-signature": "mock"})
        assert first.status_code == 200, first.text
        assert client.get("/api/billing/status", headers=owner).json()["plan"] == "pro"
        assert client.post(url, content=b"{}", headers={
            "stripe-signature": "mock"
        }).json()["duplicate"] is True
        event["id"] = "evt_" + str(uuid4())
        event["created"] = 1001
        event["data"]["object"]["items"]["data"][0]["price"]["id"] = "unrecognized"
        assert client.post(url, content=b"{}", headers={
            "stripe-signature": "mock"
        }).status_code == 200
        assert client.get("/api/billing/status", headers=owner).json()["plan"] == "free"



def test_stripe_environment_gate_never_activates_live_key_by_accident(monkeypatch):
    from app.config import settings
    from app.billing import billing_mode
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_unit_local")
    monkeypatch.setattr(settings, "stripe_price_id", "price_unit_local")
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_live_mocked_not_real")
    monkeypatch.setattr(settings, "stripe_live_billing_enabled", False)
    monkeypatch.setattr(settings, "environment", "development")
    assert billing_mode() is None
    monkeypatch.setattr(settings, "environment", "production")
    assert billing_mode() is None
    monkeypatch.setattr(settings, "stripe_live_billing_enabled", True)
    assert billing_mode() == "live"
    monkeypatch.setattr(settings, "environment", "staging")
    assert billing_mode() is None
    monkeypatch.setattr(settings, "stripe_live_billing_enabled", False)
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_mocked_not_real")
    assert billing_mode() == "test"
    monkeypatch.setattr(settings, "environment", "production")
    assert billing_mode() is None


def test_stripe_offer_rejects_wrong_mode_and_price(monkeypatch):
    from app import billing
    from app.config import settings
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_mocked_not_real")
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_unit_local")
    monkeypatch.setattr(settings, "stripe_price_id", "price_mocked")
    monkeypatch.setattr(settings, "stripe_expected_currency", "gbp")
    seen = []

    async def provider(fn, *args, **kwargs):
        seen.append(fn)
        return {"id": "price_mocked", "active": True, "livemode": True,
                "type": "recurring", "recurring": {"interval": "month"},
                "currency": "gbp", "unit_amount": 1900}
    monkeypatch.setattr(billing, "stripe_call", provider)
    with TestClient(app) as client:
        owner = register(client, identity())
        result = client.get("/api/billing/offer", headers=owner)
        assert result.status_code == 503
        result = client.post("/api/billing/checkout", headers=owner)
        assert result.status_code == 503
        assert len(seen) == 2  # Price checked; no Customer or Checkout is created.


def test_stripe_webhook_rejects_wrong_environment(monkeypatch):
    from app import billing
    from app.config import settings
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_mocked_not_real")
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_unit_local")
    monkeypatch.setattr(settings, "stripe_price_id", "price_mocked")
    monkeypatch.setattr(billing.stripe.Webhook, "construct_event",
                        lambda body, signature, secret: {
                            "id": "evt_" + str(uuid4()),
                            "type": "customer.subscription.created",
                            "livemode": True,
                            "created": 100,
                            "data": {"object": {"id": "sub_test", "customer": "cus_fake",
                                                "status": "active", "items": {"data": []}}}
                        })
    with TestClient(app) as client:
        response = client.post("/api/billing/webhook", content=b"{}",
                               headers={"stripe-signature": "unit_test_only"})
        assert response.status_code == 400



def test_real_stripe_webhook_signature_without_external_network(monkeypatch):
    """Exercise Stripe's actual signature verifier; no Stripe API call or charge."""
    import hashlib
    import hmac
    import json
    import time
    from app.config import settings

    secret = "whsec_synthetic_local_secret_only"
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_not_a_real_key")
    monkeypatch.setattr(settings, "stripe_webhook_secret", secret)
    monkeypatch.setattr(settings, "stripe_price_id", "price_nonexistent_fixture")
    event = {
        "id": "evt_" + str(uuid4()),
        "object": "event", "api_version": "2025-04-30.basil",
        "livemode": False, "created": int(time.time()),
        "type": "customer.subscription.updated",
        "data": {"object": {"id": "sub_not_real", "customer": "cus_not_real",
                            "object": "subscription", "status": "active",
                            "items": {"data": []}}}
    }
    body = json.dumps(event, separators=(",", ":")).encode()
    timestamp = int(time.time())
    signature = hmac.new(secret.encode(), str(timestamp).encode() + b"." + body,
                         hashlib.sha256).hexdigest()
    signature_header = "t=" + str(timestamp) + ",v1=" + signature
    with TestClient(app) as client:
        first = client.post("/api/billing/webhook", content=body,
                            headers={"stripe-signature": signature_header})
        assert first.status_code == 200, first.text
        duplicate = client.post("/api/billing/webhook", content=body,
                                headers={"stripe-signature": signature_header})
        assert duplicate.status_code == 200 and duplicate.json()["duplicate"] is True
        invalid = client.post("/api/billing/webhook", content=body,
                              headers={"stripe-signature": "t=123,v1=bad"})
        assert invalid.status_code == 400

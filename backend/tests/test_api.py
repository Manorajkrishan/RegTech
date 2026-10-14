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

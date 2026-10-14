import pytest
from fastapi.testclient import TestClient
from app.carbon_engine import CarbonEngine
from main import app

engine = CarbonEngine()
client = TestClient(app)

def test_actual_activity_required():
    assert engine.process_transaction("electricity bill", 500, category="electricity") is None

def test_activity_calculation_tracks_factor_year():
    result = engine.process_transaction("electricity", 500, quantity=100, unit="kWh", category="electricity")
    assert result is not None
    assert result.emissions_kg_co2e == round(result.emission_factor * 100, 2)
    assert result.factor_year == 2024

def test_wrong_unit_rejected():
    with pytest.raises(ValueError):
        engine.process_transaction("electricity", 500, quantity=100, unit="litre", category="electricity")

def test_no_fabricated_ocr_result_on_invalid_file():
    resp = client.post("/api/process-invoice", files={"file": ("fake.pdf", b"not a PDF", "application/pdf")})
    assert resp.status_code == 415

def test_missing_activity_skipped_in_batch():
    resp = client.post("/api/process-transactions", json=[{"description": "electricity", "amount_gbp": 100, "category": "electricity"}])
    assert resp.status_code == 200
    body = resp.json()
    assert body["transactions"] == []
    assert body["scorecard"]["total_kg_co2e"] == 0
    assert body["scorecard"]["skipped_count"] == 1

def test_valid_batch_scope_2():
    resp = client.post("/api/process-transactions", json=[{"description": "electricity", "amount_gbp": 100, "quantity": 200, "unit": "kWh", "category": "electricity"}])
    assert resp.status_code == 200
    assert resp.json()["scorecard"]["scope_emissions"]["Scope 2 - Purchased energy"] > 0

def test_negative_amount_rejected():
    resp = client.post("/api/process-transactions", json=[{"description": "electricity", "amount_gbp": -30}])
    assert resp.status_code == 422

def test_disallowed_extension():
    resp = client.post("/api/process-invoice", files={"file": ("bad.exe", b"abc", "application/octet-stream")})
    assert resp.status_code == 415

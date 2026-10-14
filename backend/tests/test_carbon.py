import pytest
from app.carbon_engine import CarbonEngine, CarbonInput
from app.nlp_pipeline import extract_hints
from app.ocr_service import extract_text
from fastapi import HTTPException


@pytest.fixture
def engine():
    return CarbonEngine()


def test_exact_units(engine):
    row = engine.calculate(CarbonInput(factor_id="electricity", quantity=100, unit="kWh", scope="Scope 2"))
    assert row["emissions_kg_co2e"] == round(100 * row["factor_value"], 5)
    assert row["factor_year"] == 2024


def test_wrong_units_rejected(engine):
    with pytest.raises(ValueError, match="Unit mismatch"):
        engine.calculate(CarbonInput(factor_id="electricity", quantity=100, unit="GBP", scope="Scope 2"))


def test_spend_factors_disabled(engine):
    with pytest.raises(ValueError, match="Spend-based"):
        engine.calculate(CarbonInput(factor_id="office_equipment_gbp", quantity=100, unit="GBP", scope="Scope 3"))


def test_unknown_factor_rejected(engine):
    with pytest.raises(ValueError, match="Unknown"):
        engine.calculate(CarbonInput(factor_id="not-real", quantity=100, unit="kWh", scope="Scope 2"))


def test_invoice_hints_cannot_guess_activity_from_cost():
    hints = extract_hints("Total: £300.00")
    assert hints["amount_gbp"] == 300
    assert hints["activity_hints"] == []
    assert hints["needs_review"] is True


def test_invoice_hints_activity_units():
    hints = extract_hints("Total £100\nUsage 500 kWh")
    assert hints["activity_hints"][0]["quantity"] == 500
    assert hints["activity_hints"][0]["unit"] == "kWh"


def test_invalid_file_does_not_return_sample():
    with pytest.raises(HTTPException) as error:
        extract_text(b"not a PDF or image", "fake.pdf")
    assert error.value.status_code == 415

"""Explicit activity-based conversion. Never infer kWh, km or litres from invoice cost."""
import json
from pathlib import Path
from pydantic import BaseModel, Field

from .config import settings

SOURCE_URL = "https://www.gov.uk/government/publications/greenhouse-gas-reporting-conversion-factors-2026"
VALID_SCOPES = ("Scope 1", "Scope 2", "Scope 3")


class CarbonInput(BaseModel):
    factor_id: str
    quantity: float = Field(gt=0, le=1e12)
    unit: str
    scope: str


class CarbonEngine:
    def __init__(self, path=None):
        filename = path or settings.factor_path or str(Path(__file__).resolve().parent.parent / "data" / "emission_factors.json")
        self.data = json.loads(Path(filename).read_text(encoding="utf-8"))
        self.factors = self.data["factors"]
        self.year = int(self.data.get("year", 0))
        self.source = self.data.get("source", "")

    def catalog(self):
        return {
            "factor_year": self.year,
            "source": self.source,
            "official_2026_url": SOURCE_URL,
            "warning": "Legacy 2024 curated factors; verify each mapping against official year-specific factors before external reporting." if self.year < 2026 else "Check factor scope, methodology and reporting-period applicability before external use.",
            "factors": [
                {"id": key, "name": item.get("subcategory", key),
                 "unit": item["unit"], "factor": item["emission_factor"],
                 "suggested_scope": item.get("category"), "supported": item["unit"] != "GBP"}
                for key, item in self.factors.items()
            ],
        }

    def calculate(self, request: CarbonInput) -> dict:
        factor = self.factors.get(request.factor_id)
        if factor is None:
            raise ValueError("Unknown factor")
        if factor["unit"] == "GBP":
            raise ValueError("Spend-based factors require separately validated methodology; not enabled")
        if request.unit != factor["unit"]:
            raise ValueError("Unit mismatch: expected " + factor["unit"])
        if request.scope not in VALID_SCOPES:
            raise ValueError("Scope must be explicitly selected")
        emission_factor = float(factor["emission_factor"])
        if emission_factor < 0:
            raise ValueError("Negative emission factor is invalid")
        return {
            "emissions_kg_co2e": round(request.quantity * emission_factor, 5),
            "factor_value": emission_factor,
            "factor_year": self.year,
            "factor_source": self.source,
            "suggested_scope": factor.get("category"),
        }


carbon_engine = CarbonEngine()

"""Conservative emissions calculations: activity units must match factor units."""
import json
import math
from pathlib import Path
from typing import Optional
from pydantic import BaseModel

class CarbonResult(BaseModel):
    category: str
    subcategory: str
    quantity: float
    unit: str
    emission_factor: float
    emissions_kg_co2e: float
    scope: str
    factor_year: int
    method: str = "activity-based"

class CarbonEngine:
    def __init__(self, factors_path: Optional[Path] = None):
        path = factors_path or Path(__file__).parent.parent / "data" / "emission_factors.json"
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        self.factors = data["factors"]
        self.factor_year = int(data["year"])
        self.category_keywords = data.get("category_keywords", {})

    def get_factor(self, category: str) -> Optional[dict]:
        return self.factors.get(category)

    def calculate(self, category: str, quantity: float, unit_hint: Optional[str] = None) -> Optional[CarbonResult]:
        fac = self.get_factor(category)
        if not fac:
            return None
        if not isinstance(quantity, (int, float)) or not math.isfinite(quantity) or quantity < 0:
            raise ValueError("Activity quantity must be non-negative and finite")
        if unit_hint is not None and unit_hint != fac["unit"]:
            raise ValueError(f"Unit mismatch for {category}: expected {fac['unit']}, got {unit_hint}")
        return CarbonResult(
            category=category,
            subcategory=fac["subcategory"],
            quantity=float(quantity),
            unit=fac["unit"],
            emission_factor=fac["emission_factor"],
            emissions_kg_co2e=round(quantity * fac["emission_factor"], 2),
            scope=fac["category"],
            factor_year=self.factor_year,
        )

    def classify_from_text(self, description: str, supplier: str = "") -> Optional[str]:
        text = f"{description} {supplier}".lower()
        for cat, keywords in self.category_keywords.items():
            if any(kw in text for kw in keywords):
                return cat
        mapping = [
            ("electric", "electricity"), ("natural gas", "natural_gas"),
            ("diesel", "diesel_litres"), ("train", "train_national_km"),
            ("flight", "flight_short_haul_km"), ("hotel", "hotel_night"),
            ("water", "water_m3"), ("waste", "waste_general_kg"),
        ]
        return next((cat for needle, cat in mapping if needle in text), None)

    def process_transaction(self, description: str, amount_gbp: float,
                            quantity: Optional[float] = None, unit: Optional[str] = None,
                            category: Optional[str] = None, supplier: str = "") -> Optional[CarbonResult]:
        cat = category or self.classify_from_text(description, supplier)
        fac = self.get_factor(cat) if cat else None
        if not fac:
            return None
        # GBP factors are spend-based proxies and must be explicitly labeled as such.
        if fac["unit"] == "GBP":
            if not isinstance(amount_gbp, (int, float)) or not math.isfinite(amount_gbp) or amount_gbp < 0:
                raise ValueError("Invalid GBP amount")
            result = self.calculate(cat, amount_gbp, "GBP")
            result.method = "spend-based-estimate"
            return result
        # NEVER infer kWh, litres, km or kg from the invoice amount.
        if quantity is None or not unit:
            return None
        return self.calculate(cat, float(quantity), unit)

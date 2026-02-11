"""
Carbon calculation engine - applies DEFRA emission factors to transactions.
"""
import json
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


class CarbonEngine:
    def __init__(self, factors_path: Optional[Path] = None):
        path = factors_path or Path(__file__).parent.parent / "data" / "emission_factors.json"
        with open(path) as f:
            data = json.load(f)
        self.factors = data["factors"]
        self.category_keywords = data.get("category_keywords", {})

    def get_factor(self, category: str) -> Optional[dict]:
        return self.factors.get(category)

    def calculate(self, category: str, quantity: float, unit_hint: Optional[str] = None) -> Optional[CarbonResult]:
        fac = self.get_factor(category)
        if not fac:
            return None
        factor_val = fac["emission_factor"]
        emissions = quantity * factor_val
        scope = fac["category"]
        return CarbonResult(
            category=category,
            subcategory=fac["subcategory"],
            quantity=quantity,
            unit=fac["unit"],
            emission_factor=factor_val,
            emissions_kg_co2e=round(emissions, 2),
            scope=scope,
        )

    def classify_from_text(self, description: str, supplier: str = "") -> Optional[str]:
        """Map free text to emission category using keyword matching."""
        text = f"{description} {supplier}".lower()
        for cat, keywords in self.category_keywords.items():
            if any(kw in text for kw in keywords):
                return cat
        # Fallbacks
        if "electric" in text or "power" in text:
            return "electricity"
        if "gas" in text and "natural" in text:
            return "natural_gas"
        if "diesel" in text or "fuel" in text:
            return "diesel_litres"
        if "train" in text or "rail" in text:
            return "train_national_km"
        if "flight" in text or "airline" in text:
            return "flight_short_haul_km"
        if "hotel" in text:
            return "hotel_night"
        if "delivery" in text or "freight" in text or "courier" in text:
            return "freight_road_kg_km"
        if "paper" in text or "stationery" in text:
            return "paper_tonne"
        if "laptop" in text or "computer" in text or "printer" in text:
            return "office_equipment_gbp"
        if "water" in text:
            return "water_m3"
        if "waste" in text:
            return "waste_general_kg"
        if "material" in text or "supplies" in text:
            return "generic_materials_gbp"
        return "generic_services_gbp"

    def process_transaction(self, description: str, amount_gbp: float, quantity: Optional[float] = None,
                            unit: Optional[str] = None, category: Optional[str] = None,
                            supplier: str = "") -> Optional[CarbonResult]:
        """Process a transaction and return carbon result."""
        cat = category or self.classify_from_text(description, supplier)
        fac = self.get_factor(cat)
        if not fac:
            return None

        u = fac["unit"]
        if quantity is not None and unit and unit == u:
            q = quantity
        elif u == "GBP":
            q = amount_gbp
        elif u == "kWh" and "electric" in (description + supplier).lower():
            q = quantity if quantity else amount_gbp * 0.15  # rough £/kWh
        elif u == "litre":
            q = quantity if quantity else amount_gbp / 1.5  # rough £/litre
        elif u == "km":
            q = quantity if quantity else amount_gbp * 0.15  # rough
        elif u == "night":
            q = quantity if quantity else 1
        elif u == "tonne.km":
            q = quantity if quantity else amount_gbp * 0.01
        elif u == "kg":
            q = quantity if quantity else amount_gbp * 0.5
        elif u == "m3":
            q = quantity if quantity else amount_gbp * 0.5
        else:
            q = amount_gbp  # fallback to GBP
        return self.calculate(cat, q)

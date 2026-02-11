"""
Generate synthetic invoice/transaction data for ESG platform development.
Output: JSON and CSV files in backend/data/
"""
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent / "data"

# Sample suppliers and descriptions mapped to emission categories
INVOICE_TEMPLATES = [
    # Electricity
    {"supplier": "EDF Energy", "description": "Business electricity supply", "category": "electricity", "unit": "kWh", "amount_range": (5000, 50000), "quantity_mult": 1},
    {"supplier": "Octopus Energy", "description": "Office electricity quarterly", "category": "electricity", "unit": "kWh", "amount_range": (3000, 25000), "quantity_mult": 1},
    {"supplier": "British Gas", "description": "Electricity invoice", "category": "electricity", "unit": "kWh", "amount_range": (4000, 40000), "quantity_mult": 1},
    # Gas
    {"supplier": "British Gas", "description": "Natural gas supply", "category": "natural_gas", "unit": "kWh", "amount_range": (2000, 30000), "quantity_mult": 1},
    {"supplier": "Shell Energy", "description": "Gas heating", "category": "natural_gas", "unit": "kWh", "amount_range": (1000, 20000), "quantity_mult": 1},
    # Diesel/Petrol
    {"supplier": "BP Fuel", "description": "Diesel for company vehicles", "category": "diesel_litres", "unit": "litre", "amount_range": (200, 2000), "quantity_mult": 1.5},
    {"supplier": "Shell Fuel", "description": "Petrol - business travel", "category": "petrol_litres", "unit": "litre", "amount_range": (100, 800), "quantity_mult": 1.4},
    {"supplier": "Esso", "description": "Fleet fuel", "category": "diesel_litres", "unit": "litre", "amount_range": (500, 3000), "quantity_mult": 1.5},
    # Travel
    {"supplier": "Enterprise Rent-A-Car", "description": "Business car hire - 5 days", "category": "car_diesel_km", "unit": "km", "amount_range": (200, 800), "quantity_mult": 1},
    {"supplier": "National Rail", "description": "Rail tickets London-Manchester", "category": "train_national_km", "unit": "km", "amount_range": (300, 600), "quantity_mult": 1},
    {"supplier": "TFL", "description": "Oyster business travel", "category": "train_underground_km", "unit": "km", "amount_range": (50, 300), "quantity_mult": 1},
    {"supplier": "British Airways", "description": "Flight London-Edinburgh", "category": "flight_short_haul_km", "unit": "km", "amount_range": (400, 600), "quantity_mult": 1},
    {"supplier": "Premier Inn", "description": "Hotel accommodation - 2 nights", "category": "hotel_night", "unit": "night", "amount_range": (2, 5), "quantity_mult": 1},
    {"supplier": "Travelodge", "description": "Business stay", "category": "hotel_night", "unit": "night", "amount_range": (1, 4), "quantity_mult": 1},
    # Freight
    {"supplier": "DHL", "description": "Freight delivery", "category": "freight_road_kg_km", "unit": "tonne.km", "amount_range": (500, 5000), "quantity_mult": 0.001},
    {"supplier": "DPD", "description": "Parcel delivery", "category": "freight_road_kg_km", "unit": "tonne.km", "amount_range": (100, 2000), "quantity_mult": 0.001},
    {"supplier": "UPS", "description": "International shipping", "category": "freight_sea_kg_km", "unit": "tonne.km", "amount_range": (10000, 100000), "quantity_mult": 0.00001},
    # Office
    {"supplier": "Staples", "description": "Office paper and stationery", "category": "paper_tonne", "unit": "kg", "amount_range": (50, 500), "quantity_mult": 0.001},
    {"supplier": "Viking Direct", "description": "Printer paper A4", "category": "paper_tonne", "unit": "kg", "amount_range": (100, 400), "quantity_mult": 0.001},
    {"supplier": "Dell", "description": "Laptop purchase", "category": "office_equipment_gbp", "unit": "GBP", "amount_range": (500, 1500), "quantity_mult": 1},
    {"supplier": "HP", "description": "Printer", "category": "office_equipment_gbp", "unit": "GBP", "amount_range": (200, 800), "quantity_mult": 1},
    # Water/Waste
    {"supplier": "Thames Water", "description": "Water supply", "category": "water_m3", "unit": "m3", "amount_range": (20, 200), "quantity_mult": 1},
    {"supplier": "Biffa", "description": "Waste collection", "category": "waste_general_kg", "unit": "kg", "amount_range": (500, 3000), "quantity_mult": 1},
    # Generic fallbacks
    {"supplier": "Generic Supplies Ltd", "description": "Materials", "category": "generic_materials_gbp", "unit": "GBP", "amount_range": (200, 2000), "quantity_mult": 1},
    {"supplier": "Consulting Co", "description": "Professional services", "category": "generic_services_gbp", "unit": "GBP", "amount_range": (1000, 5000), "quantity_mult": 1},
]

def generate_invoice(template: dict, invoice_id: int, base_date: datetime) -> dict:
    low, high = template["amount_range"]
    amount = round(random.uniform(low, high), 2)
    quantity = amount * template["quantity_mult"]
    quantity = round(quantity, 2)
    date = base_date - timedelta(days=random.randint(0, 365))
    return {
        "id": f"INV-{invoice_id:05d}",
        "supplier": template["supplier"],
        "description": template["description"],
        "amount_gbp": amount,
        "quantity": quantity,
        "unit": template["unit"],
        "category": template["category"],
        "date": date.strftime("%Y-%m-%d"),
        "document_type": "invoice",
    }


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    random.seed(42)
    base_date = datetime.now()
    invoices = []
    for i in range(1, 101):
        t = random.choice(INVOICE_TEMPLATES)
        invoices.append(generate_invoice(t, i, base_date))

    # Sort by date
    invoices.sort(key=lambda x: x["date"], reverse=True)

    out_json = OUTPUT_DIR / "synthetic_invoices.json"
    with open(out_json, "w") as f:
        json.dump(invoices, f, indent=2)
    print(f"Generated {len(invoices)} synthetic invoices -> {out_json}")

    # Also CSV for easy import
    import csv
    out_csv = OUTPUT_DIR / "synthetic_invoices.csv"
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=invoices[0].keys())
        w.writeheader()
        w.writerows(invoices)
    print(f"CSV saved -> {out_csv}")


if __name__ == "__main__":
    main()

"""Hints only: extraction never creates or approves an emissions record."""
import re
from datetime import datetime

KNOWN_SUPPLIERS = (
    "octopus energy", "british gas", "edf energy", "thames water",
    "dhl", "dpd", "easyjet", "national rail"
)

UNITS = {
    "kWh": r"([\d,]+(?:\.\d+)?)\s*kwh\b",
    "litre": r"([\d,]+(?:\.\d+)?)\s*(?:litres?|liters?)\b",
    "km": r"([\d,]+(?:\.\d+)?)\s*(?:km|kilometres?)\b",
    "kg": r"([\d,]+(?:\.\d+)?)\s*kg\b",
    "m3": r"([\d,]+(?:\.\d+)?)\s*(?:m3|m³)\b",
}


def extract_hints(text: str) -> dict:
    lower = text.lower()
    supplier = next((s.title() for s in KNOWN_SUPPLIERS if s in lower), None)
    amount = None
    # Prefer labelled totals, never take the first currency symbol (may be VAT/subtotal).
    matches = re.findall(r"(?:grand\s+total|total\s+due|total\s+amount|total)\s*:?\s*£?\s*([\d,]+(?:\.\d{2})?)", text, re.I)
    if matches:
        amount = float(matches[-1].replace(",", ""))
    date = None
    match = re.search(r"\b(\d{2})/(\d{2})/(\d{4})\b", text)
    if match:
        try:
            date = datetime.strptime(match.group(0), "%d/%m/%Y").date().isoformat()
        except ValueError:
            pass
    activities = []
    for unit, pattern in UNITS.items():
        for item in re.finditer(pattern, text, re.I):
            activities.append({"quantity": float(item.group(1).replace(",", "")), "unit": unit, "evidence": item.group(0)})
    return {
        "supplier": supplier, "amount_gbp": amount, "date": date,
        "activity_hints": activities[:15], "needs_review": True,
        "note": "OCR hints only. Verify quantities, factor, scope and ownership against source documents."
    }

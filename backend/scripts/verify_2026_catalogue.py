"""Cross-check selected 2026 factors against the exact official source rows."""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
raw = json.loads((ROOT / "data" / "defra_2026_raw_catalogue.json").read_text())
curated = json.loads((ROOT / "data" / "emission_factors_2026.json").read_text())
assert raw["year"] == curated["year"] == 2026
assert raw["sha256"] == curated["source_sha256"]
assert raw["status"] == "unreviewed_import_not_approved_for_calculation"
assert raw["revision"] == "31 July 2026"
sheet = {r["source_row"]: r["cells"] for r in raw["sheets"]["Factors by Category"]}
for name, factor in curated["factors"].items():
    row_number = factor["source_row"]
    row = sheet[row_number]
    assert str(row[0]) == factor["source_id"], (name, "source ID mismatch")
    assert row[1] == factor["category"], (name, "source scope mismatch")
    assert row[7] == factor["unit"], (name, "unit mismatch")
    assert row[8] == "kg CO2e", (name, "unsupported conversion column")
    assert isinstance(row[9], (float, int)), (name, "blank factor")
    assert math.isclose(row[9], factor["emission_factor"], abs_tol=1e-10), (name, "factor value mismatch")
    print(name, "source row", row_number, "=", factor["emission_factor"], "kg CO2e per", factor["unit"])
print("All", len(curated["factors"]), "selected factors match the official revised 2026 workbook.")
print("Note: independent scope/boundary/accounting validation still required.")

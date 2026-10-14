"""Transparent reporting for prototype; not an audit or certification."""
from datetime import datetime, timezone
from html import escape
from typing import List, Dict, Any

def build_esg_scorecard(transactions: List[Dict], scope_totals: Dict[str, float]) -> Dict[str, Any]:
    total = sum(scope_totals.get(k, 0) for k in ("scope1", "scope2", "scope3"))
    factors = sorted({int(t["factor_year"]) for t in transactions if t.get("factor_year")})
    return {
        "report_date": datetime.now(timezone.utc).isoformat(),
        "standards": "GHG inventory working draft (not independently assured)",
        "factor_years": factors,
        "scope_emissions": {
            "Scope 1 - Direct emissions": round(scope_totals.get("scope1", 0), 2),
            "Scope 2 - Purchased energy": round(scope_totals.get("scope2", 0), 2),
            "Scope 3 - Value chain": round(scope_totals.get("scope3", 0), 2),
        },
        "total_kg_co2e": round(total, 2),
        "total_tonnes_co2e": round(total / 1000, 2),
        "transaction_count": len(transactions),
        "breakdown_by_category": _aggregate_by_category(transactions),
        "transactions": transactions[:50],
    }

def _aggregate_by_category(transactions: List[Dict]) -> Dict[str, float]:
    agg: Dict[str, float] = {}
    for t in transactions:
        cat = t.get("category") or "Uncategorized"
        agg[cat] = agg.get(cat, 0) + (t.get("emissions_kg_co2e") or 0)
    return {k: round(v, 2) for k, v in sorted(agg.items(), key=lambda x: -x[1])}

def scorecard_to_html(scorecard: Dict) -> str:
    s = scorecard
    scope_rows = "".join(
        f"<tr><td>{escape(str(cat))}</td><td>{em:.2f}</td></tr>"
        for cat, em in s["scope_emissions"].items()
    )
    cat_rows = "".join(
        f"<tr><td>{escape(str(cat))}</td><td>{em:.2f}</td></tr>"
        for cat, em in s.get("breakdown_by_category", {}).items()
    )
    warning = escape(s.get("disclaimer", "Working draft — figures require independent review."))
    standards = escape(s["standards"])
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Emissions working draft</title>
<style>body{{font-family:Arial,sans-serif;max-width:800px;margin:40px auto;padding:20px}}
table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ddd;padding:10px;text-align:left}}
th{{background:#155e52;color:white}}.notice{{padding:15px;border:2px solid #a16207}}</style></head>
<body><h1>GHG Inventory — Working Draft</h1>
<p class="notice">{warning} Not an audit-ready regulatory filing.</p>
<p>Generated: {escape(s["report_date"])}</p><p>Basis: {standards}</p>
<p>Emissions factor years: {escape(", ".join(map(str, s.get("factor_years", []))))}</p>
<h2>Scope overview (kg CO2e)</h2><table><tr><th>Scope</th><th>kg CO2e</th></tr>{scope_rows}</table>
<p>Total: {s["total_tonnes_co2e"]} tCO2e</p>
<h2>Categories</h2><table><tr><th>Category</th><th>kg CO2e</th></tr>{cat_rows}</table>
<p>Transactions calculated: {s["transaction_count"]}; skipped: {s.get("skipped_count", 0)}.</p></body></html>"""

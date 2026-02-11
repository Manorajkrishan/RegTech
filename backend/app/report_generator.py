"""
ESG report generator - creates audit-ready scorecard data and PDF-ready content.
"""
from datetime import datetime
from typing import List, Dict, Any


def build_esg_scorecard(transactions: List[Dict], scope_totals: Dict[str, float]) -> Dict[str, Any]:
    """Build ESG scorecard structure aligned with UK SRS."""
    total = scope_totals.get("scope1", 0) + scope_totals.get("scope2", 0) + scope_totals.get("scope3", 0)
    return {
        "report_date": datetime.utcnow().isoformat(),
        "standards": "UK Sustainability Reporting Standards (UK SRS) 2026",
        "scope_emissions": {
            "Scope 1 - Direct emissions": round(scope_totals.get("scope1", 0), 2),
            "Scope 2 - Indirect (energy)": round(scope_totals.get("scope2", 0), 2),
            "Scope 3 - Value chain": round(scope_totals.get("scope3", 0), 2),
        },
        "total_kg_co2e": round(total, 2),
        "total_tonnes_co2e": round(total / 1000, 2),
        "transaction_count": len(transactions),
        "breakdown_by_category": _aggregate_by_category(transactions),
        "transactions": transactions[:50],  # Top 50 for report
    }


def _aggregate_by_category(transactions: List[Dict]) -> Dict[str, float]:
    agg = {}
    for t in transactions:
        cat = t.get("category") or "Uncategorized"
        agg[cat] = agg.get(cat, 0) + (t.get("emissions_kg_co2e") or 0)
    return {k: round(v, 2) for k, v in sorted(agg.items(), key=lambda x: -x[1])}


def scorecard_to_html(scorecard: Dict) -> str:
    """Convert scorecard to HTML for PDF export."""
    s = scorecard
    rows = "\n".join(
        f"<tr><td>{cat}</td><td>{em:.2f}</td></tr>"
        for cat, em in s["scope_emissions"].items()
    )
    cat_rows = "\n".join(
        f"<tr><td>{cat}</td><td>{em:.2f}</td></tr>"
        for cat, em in s.get("breakdown_by_category", {}).items()
    )
    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>ESG Scorecard</title>
<style>
  body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; }}
  h1 {{ color: #1a5f4a; }} h2 {{ color: #2d7a63; margin-top: 24px; }}
  table {{ border-collapse: collapse; width: 100%; margin: 16px 0; }}
  th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
  th {{ background: #1a5f4a; color: white; }}
  .total {{ font-weight: bold; font-size: 1.2em; }}
</style>
</head>
<body>
  <h1>ESG Compliance Scorecard</h1>
  <p>Generated: {s['report_date'][:19]} UTC</p>
  <p>Aligned with: {s['standards']}</p>

  <h2>Emissions Summary</h2>
  <table>
    <tr><th>Scope</th><th>kg CO2e</th></tr>
    {rows}
  </table>
  <p class="total">Total: {s['total_tonnes_co2e']} tonnes CO2e</p>

  <h2>Breakdown by Category</h2>
  <table>
    <tr><th>Category</th><th>kg CO2e</th></tr>
    {cat_rows}
  </table>

  <h2>Transaction Sample</h2>
  <p>{s['transaction_count']} transactions processed.</p>
</body>
</html>
"""

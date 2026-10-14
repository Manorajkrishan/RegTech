"""Conservative organisation-specific report. Only reviewed records are included."""
from collections import defaultdict
from datetime import datetime, timezone
from html import escape


def build_report(activities: list, org_name: str) -> dict:
    scopes = {"Scope 1": 0.0, "Scope 2": 0.0, "Scope 3": 0.0}
    categories = defaultdict(float)
    years = set()
    items = []
    for row in activities:
        scopes[row.scope] += row.emissions_kg
        categories[row.factor_id] += row.emissions_kg
        years.add(row.factor_year)
        items.append({
            "id": row.id, "description": row.description, "scope": row.scope,
            "quantity": row.quantity, "unit": row.unit, "factor_id": row.factor_id,
            "emissions_kg_co2e": row.emissions_kg, "evidence_reference": row.evidence_reference,
            "factor_year": row.factor_year, "factor_source": row.factor_source,
            "activity_date": row.activity_date
        })
    total = sum(scopes.values())
    return {
        "organisation": org_name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "Draft activity-based emissions estimate (not independently assured)",
        "disclaimer": "Not an audit, certification, UK SRS statement of compliance, or regulatory submission. Verify factor vintages, ownership, boundaries, completeness and evidence with a qualified reviewer.",
        "scope_emissions": {scope: round(value, 3) for scope, value in scopes.items()},
        "total_kg_co2e": round(total, 3), "total_tonnes_co2e": round(total / 1000, 6),
        "approved_activity_count": len(items), "factor_years": sorted(years),
        "breakdown_by_factor": {k: round(v, 3) for k, v in sorted(categories.items())},
        "activities": items,
    }


def render_html(report: dict) -> str:
    lines = "".join(
        "<tr><td>%s</td><td>%s</td></tr>" % (escape(name), value)
        for name, value in report["scope_emissions"].items()
    )
    evidence = "".join(
        "<tr><td>%s</td><td>%s</td><td>%s</td><td>%.3f</td><td>%s</td></tr>" % (
            escape(row["description"]), escape(row["factor_id"]),
            escape(str(row["quantity"]) + " " + row["unit"]),
            row["emissions_kg_co2e"], escape(row["evidence_reference"])
        ) for row in report["activities"]
    )
    return ("""<!doctype html><html><head><meta charset="utf-8">
    <title>Draft carbon inventory</title><style>body{font:15px system-ui;max-width:960px;
    margin:40px auto;color:#16312d;padding:20px}table{border-collapse:collapse;width:100%}
    td,th{border:1px solid #ccc;padding:10px;text-align:left}.warning{background:#fff5d6;padding:15px}</style>
    </head><body><h1>Draft carbon inventory — %s</h1><p>%s</p>
    <p class="warning">%s</p><h2>Scope totals (kg CO₂e)</h2><table>%s</table>
    <h2>Reviewed activity evidence</h2><table><tr><th>Description</th><th>Factor</th>
    <th>Activity</th><th>kg CO₂e</th><th>Evidence reference</th></tr>%s</table>
    <p>Factor vintages: %s. Generated: %s</p></body></html>""" % (
        escape(report["organisation"]), escape(report["status"]), escape(report["disclaimer"]),
        lines, evidence, ", ".join(str(x) for x in report["factor_years"]),
        escape(report["generated_at"])
    ))

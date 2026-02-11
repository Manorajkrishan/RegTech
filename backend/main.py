"""
ESG RegTech Platform - FastAPI Backend
"""
import json
from pathlib import Path
from typing import List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.config import settings
from app.carbon_engine import CarbonEngine
from app.nlp_pipeline import NLPPipeline
from app.ocr_service import extract_text_from_image, extract_text_from_pdf
from app.database import init_db
from app.report_generator import build_esg_scorecard, scorecard_to_html


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    pass


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

carbon_engine = CarbonEngine()
nlp = NLPPipeline(carbon_engine)

# Ensure upload dir exists
settings.upload_dir.mkdir(parents=True, exist_ok=True)


@app.get("/")
def root():
    return {"message": "ESG RegTech Platform API", "docs": "/docs"}


@app.get("/api/emission-factors")
def get_emission_factors():
    """Return emission factors dataset."""
    path = Path(__file__).parent / "data" / "emission_factors.json"
    with open(path) as f:
        return json.load(f)


@app.get("/api/synthetic-invoices")
def get_synthetic_invoices():
    """Return synthetic invoice data for demo."""
    path = Path(__file__).parent / "data" / "synthetic_invoices.json"
    if not path.exists():
        raise HTTPException(404, "Run: python scripts/generate_synthetic_invoices.py")
    with open(path) as f:
        return json.load(f)


@app.post("/api/process-invoice")
async def process_invoice(file: UploadFile = File(...)):
    """Upload invoice (PDF/image), extract text via OCR, classify, calculate emissions."""
    content = await file.read()
    ext = (file.filename or "").lower().split(".")[-1]
    if ext == "pdf":
        text = extract_text_from_pdf(content)
    else:
        text = extract_text_from_image(content)

    extracted = nlp.extract_from_text(text)
    amount = extracted.get("amount") or 0
    cat = extracted.get("category") or carbon_engine.classify_from_text(text)
    result = carbon_engine.process_transaction(
        description=extracted.get("description") or text[:200],
        amount_gbp=amount,
        category=cat,
        supplier=extracted.get("supplier") or "",
    )
    if result:
        return {
            "extracted": extracted,
            "carbon_result": result.model_dump(),
            "text_preview": text[:500],
        }
    return {"extracted": extracted, "carbon_result": None, "text_preview": text[:500]}


@app.post("/api/process-transactions")
def process_transactions(transactions: List[dict]):
    """Process a batch of transactions and return emissions + scorecard."""
    results = []
    scope1, scope2, scope3 = 0.0, 0.0, 0.0
    for t in transactions:
        desc = t.get("description", "")
        amount = float(t.get("amount_gbp", 0))
        qty = t.get("quantity")
        unit = t.get("unit")
        cat = t.get("category")
        supplier = t.get("supplier", "")
        r = carbon_engine.process_transaction(desc, amount, qty, unit, cat, supplier)
        if r:
            row = {
                **t,
                "category": r.category,
                "emissions_kg_co2e": r.emissions_kg_co2e,
                "scope": r.scope,
            }
            results.append(row)
            if "Scope 1" in r.scope:
                scope1 += r.emissions_kg_co2e
            elif "Scope 2" in r.scope:
                scope2 += r.emissions_kg_co2e
            else:
                scope3 += r.emissions_kg_co2e

    scorecard = build_esg_scorecard(results, {"scope1": scope1, "scope2": scope2, "scope3": scope3})
    return {"transactions": results, "scorecard": scorecard}


@app.get("/api/scorecard-html")
def get_scorecard_html():
    """Load synthetic data, process, return HTML report."""
    path = Path(__file__).parent / "data" / "synthetic_invoices.json"
    if not path.exists():
        raise HTTPException(404, "Run: python scripts/generate_synthetic_invoices.py")
    with open(path) as f:
        invoices = json.load(f)
    tx = [{"description": i["description"], "amount_gbp": i["amount_gbp"], "quantity": i["quantity"],
           "unit": i["unit"], "category": i["category"], "supplier": i["supplier"]} for i in invoices[:30]]
    resp = process_transactions(tx)
    html = scorecard_to_html(resp["scorecard"])
    return HTMLResponse(html)


@app.get("/api/classify")
def classify_text(description: str, supplier: str = ""):
    """Classify transaction text to emission category."""
    cat = carbon_engine.classify_from_text(description, supplier)
    return {"category": cat}

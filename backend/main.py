"""RegTech API: demo mode only until organisation authentication is added."""
import json
from pathlib import Path
from typing import List, Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, ConfigDict
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

app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins, allow_methods=["GET", "POST"], allow_headers=["Content-Type"])
carbon_engine = CarbonEngine()
nlp = NLPPipeline(carbon_engine)

class TransactionInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    description: str = Field(min_length=1, max_length=2000)
    supplier: str = Field(default="", max_length=255)
    amount_gbp: float = Field(default=0, ge=0)
    quantity: Optional[float] = Field(default=None, ge=0)
    unit: Optional[str] = None
    category: Optional[str] = None

@app.get("/")
def root():
    return {"message": "RegTech prototype API", "status": "demo-not-audited", "factor_year": carbon_engine.factor_year}

@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.get("/api/emission-factors")
def get_emission_factors():
    with open(Path(__file__).parent / "data" / "emission_factors.json", encoding="utf-8") as fh:
        return json.load(fh)

@app.get("/api/synthetic-invoices")
def get_synthetic_invoices():
    with open(Path(__file__).parent / "data" / "synthetic_invoices.json", encoding="utf-8") as fh:
        return json.load(fh)

@app.post("/api/process-invoice")
async def process_invoice(file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".pdf", ".png", ".jpg", ".jpeg", ".webp"}:
        raise HTTPException(415, "Only PDF, PNG, JPEG or WebP are supported")
    content = await file.read(settings.max_upload_size + 1)
    if not content:
        raise HTTPException(400, "Empty upload")
    if len(content) > settings.max_upload_size:
        raise HTTPException(413, "Upload exceeds configured size limit")
    if suffix == ".pdf" and not content.startswith(b"%PDF"):
        raise HTTPException(415, "Invalid PDF content")
    if suffix != ".pdf" and not content.startswith((b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"RIFF")):
        raise HTTPException(415, "Invalid image content")
    text = extract_text_from_pdf(content) if suffix == ".pdf" else extract_text_from_image(content)
    extracted = nlp.extract_from_text(text)
    # OCR currently extracts invoice spend, not dependable physical activity quantities.
    # Never generate emissions from implied quantities or a guessed category.
    return {"extracted": extracted, "carbon_result": None, "review_required": True,
            "reason": "Enter verified activity quantity and matching unit before emissions calculation",
            "text_preview": text[:500]}

@app.post("/api/process-transactions")
def process_transactions(transactions: List[TransactionInput]):
    if len(transactions) > 1000:
        raise HTTPException(413, "Maximum 1000 transactions per request")
    results, skipped = [], []
    totals = {"scope1": 0.0, "scope2": 0.0, "scope3": 0.0}
    for index, t in enumerate(transactions):
        payload = t.model_dump()
        try:
            result = carbon_engine.process_transaction(**payload)
        except ValueError as exc:
            skipped.append({"index": index, "reason": str(exc)})
            continue
        if not result:
            skipped.append({"index": index, "reason": "Unknown factor or verified quantity/unit missing"})
            continue
        row = {**payload, "category": result.category, "emissions_kg_co2e": result.emissions_kg_co2e,
               "scope": result.scope, "calculation_method": result.method, "factor_year": result.factor_year}
        results.append(row)
        if result.scope == "Scope 1":
            totals["scope1"] += result.emissions_kg_co2e
        elif result.scope == "Scope 2":
            totals["scope2"] += result.emissions_kg_co2e
        else:
            totals["scope3"] += result.emissions_kg_co2e
    scorecard = build_esg_scorecard(results, totals)
    scorecard["skipped_count"] = len(skipped)
    scorecard["disclaimer"] = "Estimates for review, not verified or UK SRS-compliant disclosures."
    return {"transactions": results, "skipped": skipped, "scorecard": scorecard}

@app.get("/api/scorecard-html")
def get_scorecard_html():
    invoices = get_synthetic_invoices()
    clean = [TransactionInput(**{k: v for k, v in x.items() if k in TransactionInput.model_fields}) for x in invoices[:30]]
    summary = process_transactions(clean)
    return HTMLResponse(scorecard_to_html(summary["scorecard"]))

@app.get("/api/classify")
def classify_text(description: str, supplier: str = ""):
    return {"category": carbon_engine.classify_from_text(description, supplier), "review_required": True}

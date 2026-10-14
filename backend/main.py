"""RegTech API: review-first multi-organisation carbon inventory."""
import csv
import io
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import Activity, AuditEvent, Organisation, User, get_db, init_db
from app.security import access_token, current_user, hash_password, verify_password
from app.carbon_engine import carbon_engine, CarbonInput
from app.nlp_pipeline import extract_hints
from app.ocr_service import extract_text
from app.report_generator import build_report, render_html


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title=settings.app_name, version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in settings.cors_origins.split(",") if x.strip()],
    allow_credentials=False, allow_methods=["GET", "POST", "PUT", "PATCH"],
    allow_headers=["Authorization", "Content-Type"],
)


class Register(BaseModel):
    organisation: str = Field(min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


class Login(BaseModel):
    email: EmailStr
    password: str


class ActivityIn(BaseModel):
    description: str = Field(min_length=3, max_length=1000)
    supplier: str = Field(default="", max_length=200)
    activity_date: str = Field(min_length=10, max_length=10)
    factor_id: str
    quantity: float = Field(gt=0, le=1e12)
    unit: str
    scope: Literal["Scope 1", "Scope 2", "Scope 3"]
    evidence_reference: str = Field(min_length=3, max_length=1000)


def serialize_activity(row):
    return {
        "id": row.id, "description": row.description, "supplier": row.supplier,
        "activity_date": row.activity_date, "factor_id": row.factor_id,
        "factor_year": row.factor_year, "factor_value": row.factor_value,
        "factor_source": row.factor_source, "quantity": row.quantity, "unit": row.unit,
        "scope": row.scope, "emissions_kg_co2e": row.emissions_kg,
        "evidence_reference": row.evidence_reference, "status": row.status,
        "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
    }


async def get_activity(db, user, activity_id):
    row = await db.scalar(
        select(Activity).where(Activity.id == activity_id, Activity.org_id == user.org_id)
    )
    if not row:
        raise HTTPException(404, "Activity not found")
    return row


def audit(user, row, action):
    return AuditEvent(
        org_id=user.org_id, actor_id=user.id, activity_id=row.id,
        action=action, details="%s: %.5f %s (%s) = %.5f kg CO2e" % (
            row.factor_id, row.quantity, row.unit, row.scope, row.emissions_kg
        ),
    )


def set_activity(row, payload):
    try:
        activity_year = date.fromisoformat(payload.activity_date).year
    except ValueError as error:
        raise HTTPException(422, "Activity date must be a valid ISO date") from error
    if activity_year != carbon_engine.year:
        raise HTTPException(422, "Activity year must match the selected emission factor vintage (" + str(carbon_engine.year) + ")")
    try:
        result = carbon_engine.calculate(CarbonInput(
            factor_id=payload.factor_id, quantity=payload.quantity,
            unit=payload.unit, scope=payload.scope
        ))
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    row.description = payload.description
    row.supplier = payload.supplier
    row.activity_date = payload.activity_date
    row.factor_id = payload.factor_id
    row.factor_year = result["factor_year"]
    row.factor_value = result["factor_value"]
    row.factor_source = result["factor_source"]
    row.quantity = payload.quantity
    row.unit = payload.unit
    row.scope = payload.scope
    row.evidence_reference = payload.evidence_reference
    row.emissions_kg = result["emissions_kg_co2e"]


@app.get("/healthz")
def health():
    return {"status": "ok"}


@app.post("/api/auth/register", status_code=201)
async def register(payload: Register, db: AsyncSession = Depends(get_db)):
    email = str(payload.email).strip().lower()
    if await db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(409, "Email already registered")
    organisation = Organisation(name=payload.organisation.strip())
    db.add(organisation)
    await db.flush()
    user = User(org_id=organisation.id, email=email,
                password_hash=hash_password(payload.password), role="owner")
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        raise HTTPException(409, "Email already registered") from error
    return {"access_token": access_token(user), "token_type": "bearer"}


@app.post("/api/auth/login")
async def login(payload: Login, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.email == str(payload.email).lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Invalid credentials")
    return {"access_token": access_token(user), "token_type": "bearer"}


@app.get("/api/me")
async def me(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    organisation = await db.get(Organisation, user.org_id)
    return {"email": user.email, "role": user.role, "organisation": organisation.name}


@app.get("/api/factors")
def factors(user: User = Depends(current_user)):
    return carbon_engine.catalog()


@app.post("/api/invoices/extract")
async def invoice_hints(file: UploadFile = File(...), user: User = Depends(current_user)):
    contents = await file.read(settings.max_upload_size + 1)
    if len(contents) > settings.max_upload_size:
        raise HTTPException(413, "Maximum upload is 8 MB")
    if not contents:
        raise HTTPException(422, "Empty upload")
    text = extract_text(contents, file.filename or "")
    return {
        "extracted": extract_hints(text),
        "text_preview": text[:2000],
        "stored": False,
        "warning": "Nothing has been submitted to your carbon inventory. Review the original document."
    }


@app.get("/api/activities")
async def list_activities(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    result = await db.scalars(
        select(Activity).where(Activity.org_id == user.org_id)
        .order_by(Activity.created_at.desc()).limit(500)
    )
    return [serialize_activity(row) for row in result.all()]


@app.post("/api/activities", status_code=201)
async def create_activity(
    payload: ActivityIn, user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db)
):
    row = Activity(org_id=user.org_id, created_by=user.id)
    set_activity(row, payload)
    db.add(row)
    await db.flush()
    db.add(audit(user, row, "create_draft"))
    await db.commit()
    return serialize_activity(row)


@app.put("/api/activities/{activity_id}")
async def edit_activity(
    activity_id: str, payload: ActivityIn,
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    row = await get_activity(db, user, activity_id)
    if row.status != "draft":
        raise HTTPException(409, "Only draft activities may be edited")
    set_activity(row, payload)
    db.add(audit(user, row, "edit_draft"))
    await db.commit()
    return serialize_activity(row)


@app.patch("/api/activities/{activity_id}/approve")
async def approve_activity(
    activity_id: str, user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db)
):
    row = await get_activity(db, user, activity_id)
    if row.status != "draft":
        raise HTTPException(409, "Only drafts may be approved")
    row.status = "approved"
    row.reviewed_at = datetime.now(timezone.utc)
    db.add(audit(user, row, "approve"))
    await db.commit()
    return serialize_activity(row)


@app.patch("/api/activities/{activity_id}/void")
async def void_activity(
    activity_id: str, user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db)
):
    row = await get_activity(db, user, activity_id)
    if row.status == "void":
        raise HTTPException(409, "Already void")
    row.status = "void"
    db.add(audit(user, row, "void"))
    await db.commit()
    return serialize_activity(row)


async def report_for_org(db, user):
    org = await db.get(Organisation, user.org_id)
    rows = await db.scalars(
        select(Activity).where(Activity.org_id == user.org_id, Activity.status == "approved")
        .order_by(Activity.created_at)
    )
    return build_report(rows.all(), org.name)


@app.get("/api/reports/summary")
async def summary(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    return await report_for_org(db, user)


@app.get("/api/reports/html", response_class=HTMLResponse)
async def report_html(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    return HTMLResponse(render_html(await report_for_org(db, user)),
                        headers={"Cache-Control": "no-store"})


@app.get("/api/reports/csv")
async def report_csv(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    report = await report_for_org(db, user)
    output = io.StringIO()
    writer = csv.writer(output)
    columns = ("description", "factor_id", "factor_year", "factor_source",
               "quantity", "unit", "scope", "emissions_kg_co2e", "evidence_reference")
    writer.writerow(columns)
    for row in report["activities"]:
        writer.writerow(["'" + str(row[key]) if str(row[key]).startswith(("=", "+", "-", "@"))
                         else row[key] for key in columns])
    return Response(
        output.getvalue(), media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=carbon-inventory.csv",
                 "Cache-Control": "no-store"}
    )


@app.get("/api/audit")
async def audit_trail(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    result = await db.scalars(
        select(AuditEvent).where(AuditEvent.org_id == user.org_id)
        .order_by(AuditEvent.created_at.desc()).limit(500)
    )
    return [
        {"id": x.id, "action": x.action, "activity_id": x.activity_id,
         "details": x.details, "created_at": x.created_at.isoformat()}
        for x in result.all()
    ]

# RegTech Carbon Workspace

**Early-access pilot: human-reviewed carbon activity accounting for SMEs.**

A Next.js + FastAPI workspace for organisations to record measured emissions activities with evidence, review entries and export *draft* inventory reports. This is **not certified**, audit-ready, guaranteed UK SRS-compliant, or a replacement for professional advice.

## What has changed

- Organisation-scoped accounts, strong password hashing, short-lived JWTs and explicit production configuration
- A draft → review → approve / void workflow with immutable audit-event records
- Activity-based measurements only: **no inventing kWh, kilometres or litres from invoice costs**; activity date must match the selected factor vintage
- PDF/image OCR that **fails closed** when the document cannot be read; no mock British Gas invoice fallback
- Reviewed activity reports only, with source/year metadata, evidence reference and clear limitations
- Draft report HTML download and CSV export; refreshed premium UI and mobile layout
- Integration/unit tests and GitHub Actions build checks
- A reproducible importer for the **official July 2026 revised DEFRA/DESNZ factors workbook** into an **unreviewed** catalogue

## Critical factor-data restriction

The application now loads `backend/data/emission_factors_2026.json` by default. It contains a **selected 11-factor subset** reconciled by source row/ID, unit, scope and kg CO2e amount against the official revised July 2026 flat workbook (SHA-256: `a9a455ab396dae226d510c7be6233748416d490c41a5d20f3dc7a0c45feecd5e`). These calculations are still **not an independently assured carbon inventory or UK SRS-compliant disclosure**: users must verify activity quantities, reporting boundaries, ownership, completeness and methodology. The old 2024 sample remains stored separately for historical reference and tests.

The 2026 UK government flat file is officially maintained here:

https://www.gov.uk/government/publications/greenhouse-gas-reporting-conversion-factors-2026

The UK Government revised its **2026 machine-readable flat workbook on 31 July 2026**, correcting blank-vs-zero values. To obtain it:

```bash
cd backend
pip install -r requirements.txt
python scripts/sync_defra_2026.py
```

The importer downloads that workbook from the official assets domain and writes `backend/data/defra_2026_raw_catalogue.json` with every source row, a SHA-256 digest, original units, and retrieval metadata. The importer creates an unreviewed full catalogue and `python scripts/verify_2026_catalogue.py` reconciles every selected active factor against exact workbook rows. This does **not** automatically activate all 8,746 raw rows. A sustainability/accounting reviewer must still reconcile reporting boundaries, methodology, applicability, and any expansion of the curated subset before external reporting. A reviewed future JSON set can be activated using `FACTOR_PATH`. Do not infer factor values from monetary transaction totals. Never relabel 2024 mappings as 2026.

UK SRS S1/S2 describe broader sustainability disclosures; a carbon scorecard alone does not establish alignment or reporting obligations. For listed issuers, check FCA rules effective for accounting periods starting **1 January 2027**. SME applicability is not automatic.

## Local development

Requires Python 3.12+, Node 20+, and npm. Image OCR needs the **Tesseract executable** on PATH; scanned PDFs additionally need **Poppler**. Text-based PDFs can be extracted without those tools.

```bash
cd backend
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp ../.env.example .env   # copy manually on Windows
# set SECRET_KEY to a random value (python -c "import secrets; print(secrets.token_urlsafe(48))")
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

In another terminal:

```bash
cd frontend
npm ci
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev
```

Visit http://localhost:3000, create a workspace, add draft activities, review and approve them to generate a draft inventory. API docs are at http://127.0.0.1:8000/docs.

## Tests

```bash
cd backend
python -m pytest -q
cd ../frontend
npm run build
```

GitHub Actions also runs these checks on every PR. Passing checks is not an independent accuracy assessment or security penetration test.

## Production restrictions

Do **not** publicly deploy this pilot with customer data before the following operational controls are in place:

1. Set `ENVIRONMENT=production`, a strong `SECRET_KEY`, a restricted `CORS_ORIGINS`, a persistent managed Postgres `DB_URL` (using `postgresql+asyncpg://...`), HTTPS and a properly maintained secrets store.
2. Add migrations (Alembic), backup/restore drills, uptime monitoring, email verification/recovery, access management, session revocation and operational incident procedures.
3. Apply gateway-level rate limiting, abuse/bot protection, request monitoring, data retention/deletion, security headers, vulnerability scanning and an external security review.
4. Independently reconcile the current year's emission factors to official source rows and test real invoices. Validate scope/boundary rules with a qualified GHG accountant.
5. Define privacy notices, UK GDPR controller/processor agreements, retention policy, lawful basis, processor locations and insurance requirements.
6. Run end-to-end user acceptance tests, tenant-isolation tests, load tests, accessibility checks and a real SME pilot.
7. Add billing/organisation invitations only after security and reporting accuracy are validated.

**Important pilot limitations:** only a single owner account per organisation, self-service sign-up without verified email, no password reset, tokens in memory (sign-in needed after refresh), no subscriptions or integrations, no factor reconciliation workflow, no tax/legal compliance claims.

## Routes

- `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/me`
- `GET /api/factors`, `POST /api/invoices/extract` (preview only)
- `GET|POST /api/activities`, `PUT /api/activities/{id}`
- `PATCH /api/activities/{id}/approve`, `PATCH /api/activities/{id}/void`
- `GET /api/reports/summary`, `GET /api/reports/html`, `GET /api/reports/csv`, `GET /api/audit`
- `GET /healthz`

All routes except health and auth are bearer-protected; tenant queries use `org_id` from the signed JWT subject. Export responses are authenticated and non-cacheable.

## Product direction

Initial customers: UK small businesses and accountants preparing evidence for voluntary carbon accounting, supplier questionnaires or early emissions baselines. Proposed paid features after validation: multi-user permissions, industry templates, Xero/Sage importers, meter data capture, assurance reviewer access, billing, configurable year-specific factors, supplier collaboration and verified export formats.

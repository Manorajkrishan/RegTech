# RegTech: safe prototype foundation

This repository is a **prototype**, not a verified compliance SaaS, emissions audit, or certified UK SRS report.

## What works
- Next.js demo dashboard with synthetic invoices and API client
- FastAPI classification, OCR extraction, and carbon calculations
- Reviewed physical activity calculations with explicit units
- Skipped records when physical activity data cannot be verified
- Test suite for invalid uploads and carbon calculations

## Risk controls
- OCR failures return errors, not fabricated invoice data.
- Uploaded invoices are **not** automatically counted as emissions. Verify consumption and units first.
- Existing curated factors are **2024 examples**; they are **not** a validated 2026 factor catalog.
- The repository is not suitable for storing customer invoices or personal data.
- No authentication or tenant isolation; don't expose this API publicly or use live customer data.
- Review Scope classifications and factor source provenance before regulatory use.
- Expense-based proxy calculations are only estimates; never silently substitute spend for energy use.

## Dataset upgrade required
Use the official 2026 DESNZ/DEFRA conversion factors, **July 2026 corrected flat file**, from:
https://www.gov.uk/government/publications/greenhouse-gas-reporting-conversion-factors-2026

Before replacing factor values, implement a tested import mapping for:
activity category, unit, scope, emission-factor component, geography, valid reporting year, dataset revision, source reference. Validate sample figures against the published spreadsheet and methodology, with reviewer sign-off. **Do not relabel 2024 values as 2026 values.**

UK SRS S1/S2 official resources:
https://www.gov.uk/government/publications/uk-sustainability-reporting-standards-uk-srs-s1-and-uk-srs-s2

## Developer instructions
Backend:
```sh
cd backend
python -m venv .venv
pip install -r requirements.txt pytest
uvicorn main:app --reload
pytest -q tests
```
Install Tesseract and Poppler at OS level for OCR. Frontend:
```sh
cd frontend
npm ci
npm run dev
```

## Next launch milestones
1. Tenant-isolated organisation accounts, RBAC, secrets management and audit events.
2. Authenticated API, database migrations, encrypted document storage, retention/deletion.
3. Human verification workflow with immutable inputs and factor provenance.
4. Validated 2026 official factors and transparent Scope 1/2/3 boundaries.
5. Deployment and monitoring, automated E2E tests, third-party security review.
6. Accountant/ESG professional pilot validation before any paid compliance claim.

# RegTech v0.4 — end-to-end private pilot runbook

RegTech is still a **development pilot**, not a certified UK reporting solution or
a production deployment. The Docker Compose stack binds frontend and API to
**127.0.0.1 only**. Never expose these ports to the public internet.

## Private local setup

1. Install Docker Engine + Compose v2 and clone the repository.
2. Create a local `.env` in the repository root (never commit it).
3. Generate two independent random hex strings with:
   `python -c "import secrets; print(secrets.token_hex(32))"`.
4. Put `REGTECH_DB_PASSWORD=...` and `REGTECH_SECRET_KEY=...` in `.env`.
5. Run `docker compose config -q` followed by `docker compose up --build -d`.
6. Open **http://127.0.0.1:3000**; docs at **http://127.0.0.1:8000/docs**.
7. Troubleshoot: `docker compose logs --tail=120 api web db`.
8. Backup: `docker compose exec -T db pg_dump -U regtech -d regtech > local-backup.sql`.
   Encrypt and safeguard this SQL file. To stop: `docker compose down`.

Compose uses **development mode**: email verification runs through Mailpit
and database tables are automatically created. It is strictly for local testing, **not real customers**.
Local email is captured by Mailpit at **http://127.0.0.1:8025**. It is a
non-delivering SMTP sink, accessible from localhost only. Send an invitation
or password reset, then open Mailpit to copy the one-time link. These emails
are never delivered to the real internet by the local pilot. Stripe billing is disabled until credentials and an
approved Stripe Price ID are configured on a controlled staging service.

## Customer product journey

1. Register as the owner of an isolated organisation workspace.
2. From Activities, enter metered physical quantities with reference evidence
   (or download the CSV template and import 1–100 validated records atomically).
3. OCR invoices can suggest physical measurements, but uploads are not saved
   as evidence and no extracted suggestion is automatically approved.
4. Owner sends one-time seven-day email invitations for editor, reviewer or viewer.
   Editors can enter/edit their own drafts; reviewers can approve records by
   others; viewers can read but not edit; owners administer the workspace.
5. Approval makes an activity count toward the scope totals and draft annual
   report; voiding excludes it. Check kg CO2e/unit, source workbook row and year.
6. Free accounts can retain 25 non-voided activity records and 3 active/pending
   team seats; paid subscription removes those limits.
7. In Billing, the owner can open Stripe Checkout and the customer portal
   *only after external configuration*. **A verified subscription webhook**
   — not the browser redirect — grants the Pro plan.
8. Export CSV/HTML draft inventory. These are not independently assured,
   regulatory submissions or UK SRS-compliant claims.

## Production release gates — currently incomplete

- Secure managed Postgres, reviewed migrations and backup/restore tests.
- HTTPS, private staging, WAF, shared rate limiting and verified SMTP delivery.
- Stripe test-mode checkout/portal/webhook replay, failed-payment and cancellation
  QA, sales tax/VAT, invoices, refunds and cancellation terms.
- UK GDPR/privacy/retention/deletion, signed DPA, secure object storage and
  invoice malware scanning; isolate OCR with memory/time quotas.
- Independent greenhouse-gas accountant validation (Scope 1/2/3 ownership,
  geographic factor scope, completeness and appropriate 2026 source selection).
- Browser E2E tests, threat model, penetration test, accessibility and monitoring.
- Customer interviews and validated pricing. Do not claim certification.

## Known functional constraints

Only 11 official UK 2026 factors are mapped to the app; no 2025/2027 accounting
yet. Stripe and SMTP connectors are implementation-ready but not connected.
There is no immutable third-party-assured report sign-off, no encrypted
document vault, no Xero/Sage integration, no multi-organisation member identity
and no live end-user environment. These are product work, not cosmetic tasks.

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

Compose uses **development mode**: email verification is off and the DB schema
is automatically created. It is strictly for local testing, **not real customers**.
Team invitations require independently configured SMTP; without SMTP, invite
endpoints return 503. Stripe billing is disabled until credentials and an
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

## Stripe billing isolation and pricing guard (v0.6)

RegTech is intentionally **not connected to any live Stripe account**.
An enabled Stripe connection is not itself permission to charge anyone.
For a safe sandbox setup, create an isolated **test-mode / sandbox**
Stripe account and configure the following secrets only in a private staging
secret manager (never in GitHub or screenshots):

- `STRIPE_SECRET_KEY=sk_test_...` from the selected sandbox
- `STRIPE_WEBHOOK_SECRET=whsec_...` from an actual sandbox webhook destination
- `STRIPE_PRICE_ID=price_...` for a **verified active recurring GBP** Stripe price
- `STRIPE_EXPECTED_CURRENCY=gbp` for pilot pricing
- `STRIPE_LIVE_BILLING_ENABLED=false` at all times outside an explicitly
  approved production launch

Stripe Checkout re-verifies the Price via Stripe API before creating a customer.
The API never grants paid access based on a browser redirect; verified
subscription webhooks must match the configured mode, expected Price and
organisation customer. Entitlements for an already-active subscription cannot
be silently overwritten by a different subscription under the same customer.
Out-of-order same-second cancellation/downgrade wins conservatively.
No webhook endpoint is registered in Stripe by this code.

**Before real paid rollout:** get merchant identity, price and VAT/tax treatment
approved; enable live mode deliberately in the production environment only,
configure HTTPS, dashboard webhook signing secret, invoicing, failed payments,
grace periods/cancelation policy and reconciliation. Validate all lifecycle
paths using a sandbox first. Avoid storing credentials in the repository.

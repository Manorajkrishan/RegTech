# Security & privacy notes — RegTech pilot

**Do not deploy publicly with real customer invoices or PII yet.** This repository is
not a certified regulatory reporting service or a completed security review.

## Features currently implemented

- Per-organisation database filtering and short-lived signed bearer tokens
- Revocable tokens via user session-version counter (logout/password change/reset)
- One-time SHA-256-hashed password-reset/email-verification tokens
- Production-time requirement for verified signup, SMTP credentials, HTTPS public URLs,
  restricted CORS, strong JWT secret and persistent PostgreSQL
- Account lockout on repeated login failures and per-process IP throttle
- Activity evidence references and audit trails for user-reviewed emissions records
- No fictional invoice fallback when OCR errors occur

## Required before any public deployment

1. Independent pentest including cross-tenant authorization, JWT/session replay,
   malicious PDF/image payloads and cross-origin/auth attacks.
2. Shared gateway-level rate limits, bot protection, alerts and metrics: the built-in
   in-process IP limiter cannot enforce across multiple workers or restarts.
3. Reverse proxy TLS termination, security headers, correct client-IP trust policy,
   secrets rotation, vulnerability scanning and dependency updates.
4. Verified SMTP sender domain with DKIM/SPF/DMARC and tested delivery/abuse monitoring.
5. PostgreSQL migration rehearsal on a DB copy, encrypted backups and restore drill.
6. DPA/privacy policy, data deletion/export workflow, breach response, retention periods,
   subprocessors and UK GDPR review, including invoice PII minimization.
7. Signed-off 2026 emissions factor boundaries/ownership/methodology by a qualified GHG
   accounting reviewer, plus real-document extraction accuracy measurements.
8. Role-based access, independent second-person review and immutable audit storage
   before claiming an 'audit-ready' workflow.
9. Financial/billing compliance and customer contracts before subscriptions.

## Security bug reports

Please use private repository security advisories if enabled. Do not open public issues
containing raw customer invoices, passwords, reset links, account tokens or other secrets.

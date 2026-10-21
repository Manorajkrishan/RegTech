"""GitHub Actions / Docker smoke test: real API and PostgreSQL, no external services."""
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from time import monotonic, sleep
import re

API = "http://127.0.0.1:8000"


def request(path, method="GET", body=None, token=None):
    headers = {"Accept": "application/json"}
    if body is not None:
        body = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    req = Request(API + path, data=body, method=method, headers=headers)
    try:
        with urlopen(req, timeout=12) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw and "json" in response.headers.get("Content-Type", "") else raw.decode()
    except HTTPError as exc:
        return exc.code, exc.read().decode()


assert request("/healthz")[0] == 200
assert request("/api/activities")[0] == 401
account = {
    "organisation": "Local CI Carbon Example",
    "email": "workflow-smoke@example.com",
    "password": "VeryLongSyntheticPassword_2026!"
}
status, created = request("/api/auth/register", "POST", account)
assert status == 201, (status, created)
# Local pilot emails are only captured by Mailpit; no external deliveries.
assert "Check your email" in created["detail"]
deadline = monotonic() + 18
verify_token = None
while monotonic() < deadline:
    try:
        with urlopen("http://127.0.0.1:8025/view/latest.txt", timeout=4) as result:
            body = result.read().decode()
        match = re.search(r"/#verify=([A-Za-z0-9_-]+)", body)
        if match:
            verify_token = match.group(1)
            break
    except Exception:
        pass
    sleep(0.4)
assert verify_token is not None, "Mailpit verification email never arrived"
status, response = request("/api/auth/verify-email", "POST", {"token": verify_token})
assert status == 200, (status, response)
status, logged_in = request("/api/auth/login", "POST", {
    "email": account["email"], "password": account["password"]
})
assert status == 200, (status, logged_in)
token = logged_in["access_token"]
status, me = request("/api/me", token=token)
assert status == 200 and me["organisation"] == account["organisation"]
assert me["role"] == "owner"
activity = {
    "description": "Measured office electricity",
    "supplier": "Synthetic utility supplier",
    "activity_date": "2026-01-31",
    "factor_id": "electricity",
    "quantity": 200,
    "unit": "kWh",
    "scope": "Scope 2",
    "evidence_reference": "CI synthetic meter reading only"
}
status, draft = request("/api/activities", "POST", activity, token)
assert status == 201 and draft["status"] == "draft", (status, draft)
status, before = request("/api/reports/summary?year=2026", token=token)
assert status == 200 and before["approved_activity_count"] == 0
status, approved = request("/api/activities/" + draft["id"] + "/approve", "PATCH", token=token)
assert status == 200 and approved["status"] == "approved", (status, approved)
status, after = request("/api/reports/summary?year=2026", token=token)
assert status == 200 and after["approved_activity_count"] == 1
assert after["scope_emissions"]["Scope 2"] > 0
status, csv = request("/api/reports/csv?year=2026", token=token)
assert status == 200 and "Measured office electricity" in csv
status, billing = request("/api/billing/status", token=token)
assert status == 200 and billing["plan"] == "free"
assert request("/api/auth/logout", "POST", token=token)[0] == 200
assert request("/api/me", token=token)[0] == 401
with urlopen("http://127.0.0.1:3000/", timeout=20) as response:
    assert response.status == 200
print("PASS: private end-to-end registration, tenant auth, draft approval,")
print("      official 2026 conversion, annual report, billing status,")
print("      logout revocation, and Next.js app rendering.")

"""Chromium reset-flow smoke with sandboxed Mailpit emails only."""
import json, re, time, uuid
from urllib.request import Request, urlopen
from playwright.sync_api import sync_playwright, expect

mail = "reset-" + uuid.uuid4().hex[:8] + "@example.com"
key = "Synthetic_Recovery_Password_2026!"
base = "http://127.0.0.1:3000"

def post(path, data):
    req = Request("http://127.0.0.1:8000" + path, data=json.dumps(data).encode(),
                  headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(req, timeout=12) as response:
        assert response.status in (200, 201, 202)

def link(kind):
    end = time.monotonic() + 20
    while time.monotonic() < end:
        try:
            with urlopen("http://127.0.0.1:8025/view/latest.txt", timeout=3) as response:
                body = response.read().decode()
            match = re.search(r"/#" + kind + r"=([A-Za-z0-9_-]+)", body)
            if match:
                return base + "/#" + kind + "=" + match.group(1)
        except Exception:
            pass
        time.sleep(.4)
    raise AssertionError("Missing local recovery mail")

post("/api/auth/register", {"organisation":"QA recovery", "email":mail, "password":key})
post("/api/auth/verify-email", {"token":link("verify").split("=")[-1]})
with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page()
    try:
        page.goto(base)
        page.get_by_role("button", name="Forgot your password?").click()
        page.get_by_label("Work email").fill(mail)
        page.get_by_role("button", name="Send reset link").click()
        expect(page.get_by_text("If an account exists, a reset link will be sent.")).to_be_visible()
        page.goto(link("reset"))
        expect(page.get_by_role("heading", name="Choose a new password")).to_be_visible()
        page.get_by_label("New password").fill(key + "Changed")
        page.get_by_role("button", name="Update password").click()
        expect(page.get_by_text("Password updated. Sign in again on all devices.")).to_be_visible()
        print("PASS: Chromium password reset via captured sandbox email")
    finally:
        browser.close()

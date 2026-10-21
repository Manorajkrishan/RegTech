"""Chromium team invite and independent reviewer acceptance using local Mailpit."""
import json
import re
from pathlib import Path
from time import monotonic, sleep
from urllib.request import Request, urlopen
from uuid import uuid4
from playwright.sync_api import sync_playwright, expect

APP = "http://127.0.0.1:3000"
ART = Path("qa-artifacts")
ART.mkdir(exist_ok=True)
tag = uuid4().hex[:9]
owner_email = "team-owner-" + tag + "@example.com"
reviewer_email = "team-reviewer-" + tag + "@example.com"
password = "SyntheticStrongPassword_2026!"
activity = "Independent approval " + tag


def message_url(purpose):
    until = monotonic() + 25
    while monotonic() < until:
        try:
            with urlopen("http://127.0.0.1:8025/view/latest.txt", timeout=3) as response:
                body = response.read().decode()
            found = re.search(r"http://127\.0\.0\.1:3000/#" + purpose + r"=([A-Za-z0-9_-]+)", body)
            if found:
                return APP + "/#" + purpose + "=" + found.group(1)
        except Exception:
            pass
        sleep(0.4)
    raise AssertionError("Missing local " + purpose + " email")


def register_owner():
    payload = json.dumps({
        "organisation": "Reviewer Pilot " + tag,
        "email": owner_email, "password": password
    }).encode()
    req = Request("http://127.0.0.1:8000/api/auth/register", data=payload,
                  headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(req, timeout=15) as response:
        assert response.status == 201


register_owner()
with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    owner = browser.new_page(viewport={"width": 1280, "height": 920})
    reviewer = None
    try:
        owner.goto(message_url("verify"))
        expect(owner.get_by_text("Email verified. You can sign in.")).to_be_visible()
        owner.get_by_label("Work email").fill(owner_email)
        owner.get_by_label("Password", exact=True).fill(password)
        owner.get_by_role("button", name=re.compile(r"^Sign in")).click()
        expect(owner.get_by_role("heading", name="Overview.")).to_be_visible(timeout=15000)
        owner.get_by_role("button", name=re.compile("Activity ledger")).click()
        owner.get_by_label("Activity description").fill(activity)
        owner.get_by_label("Supplier / source").fill("Synthetic data")
        owner.get_by_label("Activity date").fill("2026-02-15")
        owner.get_by_label("Emission factor").select_option("electricity")
        owner.get_by_label("Activity quantity").fill("150")
        owner.get_by_label("Scope / ownership (must verify)").select_option("Scope 2")
        owner.get_by_label("Evidence reference").fill("test meter bill")
        owner.get_by_role("button", name=re.compile("Save as draft")).click()
        expect(owner.get_by_text(activity, exact=True)).to_be_visible()
        owner.get_by_role("button", name="Team", exact=True).click()
        expect(owner.get_by_role("heading", name="Workspace members")).to_be_visible()
        owner.get_by_label("Email", exact=True).fill(reviewer_email)
        owner.get_by_label("Role", exact=True).select_option("reviewer")
        owner.get_by_role("button", name=re.compile("Send invitation")).click()
        expect(owner.get_by_text("Invitation sent. The link expires after seven days.")).to_be_visible()

        reviewer = browser.new_page(viewport={"width": 1280, "height": 900})
        reviewer.goto(message_url("invite"))
        expect(reviewer.get_by_role("heading", name="Join your team")).to_be_visible()
        reviewer.get_by_label("New password").fill(password)
        reviewer.get_by_role("button", name="Join workspace").click()
        expect(reviewer.get_by_role("heading", name="Overview.")).to_be_visible(timeout=15000)
        reviewer.get_by_role("button", name=re.compile("Activity ledger")).click()
        expect(reviewer.get_by_role("heading", name="Record an activity")).to_have_count(0)
        expect(reviewer.get_by_text(activity, exact=True)).to_be_visible()
        reviewer.get_by_role("button", name="Approve", exact=True).click()
        expect(reviewer.get_by_text("Record approved and included in your draft inventory.")).to_be_visible()
        reviewer.screenshot(path=str(ART / "team-reviewer-approved.png"), full_page=True)

        owner.get_by_role("button", name=re.compile("Sign out")).click()
        expect(owner.get_by_role("heading", name="Welcome back")).to_be_visible()
        owner.get_by_role("button", name="Forgot your password?").click()
        owner.get_by_label("Work email").fill(owner_email)
        owner.get_by_role("button", name="Send reset link").click()
        expect(owner.get_by_text("If an account exists, a reset link will be sent.")).to_be_visible()
        owner.goto(message_url("reset"))
        expect(owner.get_by_role("heading", name="Choose a new password")).to_be_visible()
        owner.get_by_label("New password").fill("AnotherSyntheticPassword_2026!")
        owner.get_by_role("button", name="Update password").click()
        expect(owner.get_by_text("Password updated. Sign in again on all devices.")).to_be_visible()
        owner.screenshot(path=str(ART / "account-recovery.png"), full_page=True)
        print("PASS: UI owner invitation, real Mailpit email, reviewer-only approval and reset")
    except Exception:
        owner.screenshot(path=str(ART / "team-owner-failure.png"), full_page=True)
        if reviewer:
            reviewer.screenshot(path=str(ART / "team-reviewer-failure.png"), full_page=True)
        raise
    finally:
        browser.close()

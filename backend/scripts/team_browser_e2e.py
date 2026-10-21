"""Synthetic Chromium test: owner invites reviewer who approves a real DB draft."""
import re
from pathlib import Path
from time import monotonic, sleep
from urllib.request import Request, urlopen
import json
from uuid import uuid4
from playwright.sync_api import sync_playwright, expect

BASE = "http://127.0.0.1:3000"
tag = uuid4().hex[:8]
owner_email = "e2e-owner-" + tag + "@example.com"
reviewer_email = "e2e-reviewer-" + tag + "@example.com"
password = "SyntheticStrongPassword_2026!"
description = "Reviewer sample " + tag
Path("qa-artifacts").mkdir(exist_ok=True)


def mail(kind):
    stop = monotonic() + 25
    while monotonic() < stop:
        try:
            with urlopen("http://127.0.0.1:8025/view/latest.txt", timeout=3) as r:
                body = r.read().decode()
            m = re.search(r"http://127\.0\.0\.1:3000/#" + kind + r"=([A-Za-z0-9_-]+)", body)
            if m:
                return BASE + "/#" + kind + "=" + m.group(1)
        except Exception:
            pass
        sleep(0.4)
    raise AssertionError("No captured email for " + kind)


payload = json.dumps({"organisation": "E2E " + tag, "email": owner_email, "password": password}).encode()
with urlopen(Request("http://127.0.0.1:8000/api/auth/register", data=payload,
                     headers={"Content-Type": "application/json"}, method="POST"), timeout=15) as r:
    assert r.status == 201

with sync_playwright() as p:
    browser = p.chromium.launch()
    owner = browser.new_page()
    reviewer = None
    try:
        owner.goto(mail("verify"))
        expect(owner.get_by_text("Email verified. You can sign in.")).to_be_visible()
        owner.get_by_label("Work email").fill(owner_email)
        owner.get_by_label("Password", exact=True).fill(password)
        owner.get_by_role("button", name=re.compile("^Sign in")).click()
        expect(owner.get_by_role("heading", name="Overview.")).to_be_visible(timeout=15000)
        owner.get_by_role("button", name=re.compile("Activity ledger")).click()
        owner.get_by_label("Activity description").fill(description)
        owner.get_by_label("Supplier / source").fill("Test utility")
        owner.get_by_label("Activity date").fill("2026-02-15")
        owner.get_by_label("Emission factor").select_option("electricity")
        owner.get_by_label("Activity quantity").fill("150")
        owner.get_by_label("Scope / ownership (must verify)").select_option("Scope 2")
        owner.get_by_label("Evidence reference").fill("synthetic-e2e-meter")
        owner.get_by_role("button", name=re.compile("Save as draft")).click()
        expect(owner.get_by_text(description, exact=True)).to_be_visible()
        owner.get_by_role("button", name=re.compile("Team")).click()
        expect(owner.get_by_role("heading", name="Workspace members")).to_be_visible()
        owner.get_by_label("Email", exact=True).fill(reviewer_email)
        owner.get_by_label("Role").select_option("reviewer")
        owner.get_by_role("button", name=re.compile("Send invitation")).click()
        expect(owner.get_by_text("Invitation sent. The link expires after seven days.")).to_be_visible()

        reviewer = browser.new_page()
        reviewer.goto(mail("invite"))
        expect(reviewer.get_by_role("heading", name="Join your team")).to_be_visible()
        reviewer.get_by_label("New password").fill(password)
        reviewer.get_by_role("button", name="Join workspace").click()
        expect(reviewer.get_by_role("heading", name="Overview.")).to_be_visible(timeout=15000)
        reviewer.get_by_role("button", name=re.compile("Activity ledger")).click()
        expect(reviewer.get_by_role("heading", name="Record an activity")).to_have_count(0)
        expect(reviewer.get_by_text(description, exact=True)).to_be_visible()
        reviewer.get_by_role("button", name="Approve", exact=True).click()
        expect(reviewer.get_by_text("Record approved and included in your draft inventory.")).to_be_visible()
        reviewer.screenshot(path="qa-artifacts/reviewer.png")
        print("PASS: owner invitation, captured email, reviewer-only permissions and approval")
    except Exception:
        owner.screenshot(path="qa-artifacts/team-owner-fail.png")
        if reviewer is not None:
            reviewer.screenshot(path="qa-artifacts/team-reviewer-fail.png")
        raise
    finally:
        browser.close()

"""Chromium acceptance test for the private RegTech + Mailpit Compose stack."""
import re
from pathlib import Path
from time import monotonic, sleep
from urllib.request import urlopen
from uuid import uuid4
from playwright.sync_api import sync_playwright, expect

APP = "http://127.0.0.1:3000"
ART = Path("qa-artifacts")
ART.mkdir(exist_ok=True)
tag = uuid4().hex[:9]
email = "e2e-" + tag + "@example.com"
password = "DemoOnly_Strong_Password_2026!"
activity_name = "Synthetic electricity " + tag


def message_link(purpose):
    deadline = monotonic() + 25
    while monotonic() < deadline:
        try:
            with urlopen("http://127.0.0.1:8025/view/latest.txt", timeout=3) as response:
                text = response.read().decode()
            match = re.search(r"http://127\.0\.0\.1:3000/#" + purpose + r"=([A-Za-z0-9_-]+)", text)
            if match:
                return APP + "/#" + purpose + "=" + match.group(1)
        except Exception:
            pass
        sleep(0.4)
    raise AssertionError("Mailpit email missing for " + purpose)


with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page(accept_downloads=True, viewport={"width": 1400, "height": 900})
    try:
        page.goto(APP)
        page.get_by_role("button", name="New to RegTech? Create a workspace").click()
        page.get_by_label("Organisation name").fill("E2E Org " + tag)
        page.get_by_label("Work email").fill(email)
        page.get_by_label("Password", exact=True).fill(password)
        page.get_by_role("button", name="Create workspace").click()
        expect(page.get_by_text("Check your email to verify your account before signing in.")).to_be_visible()
        page.goto(message_link("verify"))
        expect(page.get_by_text("Email verified. You can sign in.")).to_be_visible()
        page.get_by_label("Work email").fill(email)
        page.get_by_label("Password", exact=True).fill(password)
        page.get_by_role("button", name=re.compile(r"^Sign in")).click()
        expect(page.get_by_role("heading", name="Overview.")).to_be_visible(timeout=15000)

        page.get_by_role("button", name=re.compile("Activity ledger")).click()
        page.get_by_label("Activity description").fill(activity_name)
        page.get_by_label("Supplier / source").fill("Test electricity supplier")
        page.get_by_label("Activity date").fill("2026-01-31")
        page.get_by_label("Emission factor").select_option("electricity")
        page.get_by_label("Activity quantity").fill("200")
        page.get_by_label("Scope / ownership (must verify)").select_option("Scope 2")
        page.get_by_label("Evidence reference").fill("synthetic invoice 1")
        page.get_by_role("button", name=re.compile("Save as draft")).click()
        expect(page.get_by_text(activity_name, exact=True)).to_be_visible()
        page.get_by_role("button", name="Approve", exact=True).click()
        expect(page.get_by_text("Record approved and included in your draft inventory.")).to_be_visible()
        page.get_by_role("button", name=re.compile("Overview")).click()
        with page.expect_download() as caught:
            page.get_by_role("button", name=re.compile("CSV export")).click()
        assert activity_name in caught.value.path().read_text()
        page.screenshot(path=str(ART / "carbon-overview.png"), full_page=True)
        print("PASS: Chromium signup, Mailpit verification, activity approval and CSV export")
    except Exception:
        page.screenshot(path=str(ART / "failure.png"), full_page=True)
        raise
    finally:
        browser.close()

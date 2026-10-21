import { test, expect } from "@playwright/test";

const unique = Math.random().toString(36).slice(2, 11);
const email = "regtech-browser-" + unique + "@example.com";
const password = "LocalBrowserTestStrong#2026";

test("signup, create measured activity, approve, export and sign out", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();
  await page.getByRole("button", { name: "New to RegTech? Create a workspace" }).click();
  await page.getByLabel("Organisation name").fill("QA Pilot Ltd");
  await page.getByLabel("Work email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: /Create workspace/ }).click();

  await expect(page.getByRole("heading", { name: "Overview." })).toBeVisible({ timeout: 20000 });
  await page.getByRole("button", { name: /Activity ledger/ }).click();
  await expect(page.getByRole("heading", { name: "Activity ledger." })).toBeVisible();
  await page.getByLabel("Activity description").fill("Metered office electricity");
  await page.getByLabel("Supplier / source").fill("Synthetic test energy");
  await page.getByLabel("Activity date").fill("2026-03-04");
  await page.getByLabel("Emission factor").selectOption("electricity");
  await page.getByLabel("Activity quantity").fill("225");
  await page.getByLabel("Scope / ownership (must verify)").selectOption("Scope 2");
  await page.getByLabel("Evidence reference").fill("Synthetic invoice #PW-001");
  await page.getByRole("button", { name: /Save as draft/ }).click();

  const activityRow = page.getByRole("row").filter({ hasText: "Metered office electricity" });
  await expect(activityRow).toBeVisible();
  await expect(activityRow).toContainText("draft");
  await activityRow.getByRole("button", { name: "Approve" }).click();
  await expect(activityRow).toContainText("approved");

  await page.getByRole("button", { name: /Overview/ }).click();
  await expect(page.getByText("2026 draft inventory exports")).toBeVisible();
  await expect(page.getByText("29.47")).toBeVisible(); // 225 × UK 2026 0.13096 kgCO2e/kWh
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: /CSV export/ }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("regtech-2026-activities.csv");

  await page.getByRole("button", { name: /Account security/ }).click();
  await expect(page.getByRole("heading", { name: "Account security." })).toBeVisible();
  await page.getByRole("button", { name: /Sign out/ }).click();
  await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();

  await page.getByLabel("Work email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: /^Sign in/ }).click();
  await expect(page.getByRole("heading", { name: "Overview." })).toBeVisible();
  await page.getByRole("button", { name: /Activity ledger/ }).click();
  await expect(page.getByRole("row").filter({ hasText: "Metered office electricity" })).toContainText("approved");
});

test("no automatic sign-in and no public API access", async ({ page, request }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();
  const response = await request.get("http://127.0.0.1:8000/api/activities");
  expect(response.status()).toBe(401);
});

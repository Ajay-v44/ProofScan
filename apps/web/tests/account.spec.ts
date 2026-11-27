import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";

test("account deletion removes data and revokes access on the migrated database", async ({ page, browser }) => {
  const email = `delete-${randomUUID()}@example.test`;
  const password = `Fixture-${randomUUID()}`;
  await page.setViewportSize({ width: 320, height: 844 });
  await page.goto("/account/delete");
  await page.getByRole("link", { name: "Sign in to continue" }).click();
  expect((await page.request.post("/api/v1/auth/register", { data: { email, password } })).ok()).toBeTruthy();
  const response = await page.request.post("/api/v1/verifications", { data: { label: "Deletion fixture", claims: {} } });
  expect(response.ok()).toBeTruthy();
  const verification = await response.json();
  const handoffResponse = await page.request.post("/api/v1/handoffs", {
    data: { label: "Deletion handoff", mode: "simulator" },
  });
  expect(handoffResponse.ok()).toBeTruthy();
  const handoffPath = "/api/v1/handoffs/" + (await handoffResponse.json()).id;
  for (const action of ["start", "record", "activate", "start", "record"]) {
    expect((await page.request.post(handoffPath + "/" + action, {
      data: action === "record" ? { condition: "clean" } : {},
    })).ok()).toBeTruthy();
  }
  const handoffReport = await page.request.get(handoffPath + "/report");
  expect(handoffReport.ok()).toBeTruthy();
  const verifyHandoff = "/api/v1/reports/" + (await handoffReport.json()).payload.report_id + "/verify";
  const session = (await page.context().cookies()).find(cookie => cookie.name === "proofscan_session")!.value;
  const guest = await browser.newContext({ baseURL: new URL(verification.guest_url).origin });
  try {
    const path = "/api/v1/guest/" + verification.id;
    const token = new URL(verification.guest_url).hash.slice(1);
    const post = async (suffix: string, data: unknown) => {
      const result = await guest.request.post(path + suffix, { data });
      expect(result.ok()).toBeTruthy();
      return result.json();
    };
    await post("/exchange", { token });
    await post("/consent", { accepted: true, policy_version: "2026-11-23" });
    const ticket = await post("/scan", { platform: "simulator" });
    await post("/submit", { scan_id: ticket.scan_id, challenge: ticket.challenge, platform: "simulator", fixture: "verified" });
    const shared = await post("/decision", { decision: "share" });
    const verify = "/api/v1/reports/" + shared.report_id + "/verify";
    expect((await guest.request.get(verify)).ok()).toBeTruthy();
    expect((await guest.request.get(verifyHandoff)).ok()).toBeTruthy();

    await page.goto("/account/delete");
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320);
    const field = page.getByLabel("Current password");
    await field.fill("incorrect-fixture");
    await page.getByRole("checkbox").check();
    await page.getByRole("button", { name: "Permanently delete account" }).click();
    await expect(page.getByText("Invalid password.")).toBeVisible();
    expect((await guest.request.get(verify)).ok()).toBeTruthy();
    await page.setViewportSize({ width: 1440, height: 900 });
    await field.fill(password);
    await page.getByRole("checkbox").check();
    await page.getByRole("button", { name: "Permanently delete account" }).click();
    await expect(page.getByText("Your account and workspace data were deleted.")).toBeVisible();
    expect((await guest.request.get(verify)).status()).toBe(404);
    expect((await guest.request.get(verifyHandoff)).status()).toBe(404);
    expect((await guest.request.get(path)).status()).toBe(404);
    const replay = await page.request.get("/api/v1/auth/session", { headers: { Authorization: "Bearer " + session } });
    expect(replay.status()).toBe(401);
    expect((await page.request.post("/api/v1/auth/login", { data: { email, password } })).status()).toBe(401);
  } finally {
    await guest.close();
  }
});

test("account pages work across phone and desktop widths, with one-time local recovery", async ({ page }) => {
  const email = `profile-${randomUUID()}@example.test`;
  const password = `Fixture-${randomUUID()}`;
  const replacement = `Updated-${randomUUID()}`;
  await page.setViewportSize({ width: 320, height: 844 });
  await page.goto("/sign-up?next=%2Fprofile");
  await expect(page.getByRole("heading", { name: "Create an account" })).toBeVisible();
  await page.getByLabel("Email address").fill(email);
  const passwordInput = page.getByLabel("Password", { exact: true });
  await passwordInput.fill(password);
  await page.getByRole("button", { name: "Show password" }).click();
  await expect(passwordInput).toHaveAttribute("type", "text");
  await page.getByRole("button", { name: "Hide password" }).click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByRole("heading", { name: "Your profile" })).toBeVisible();
  await page.setViewportSize({ width: 1440, height: 960 });
  await page.getByLabel("Display name").fill("Workshop Buyer");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByRole("status")).toContainText("Profile saved.");
  await page.reload();
  await expect(page.getByLabel("Display name")).toHaveValue("Workshop Buyer");
  await page.getByRole("button", { name: "Generate recovery code" }).click();
  const code = await page.getByLabel("New recovery code").inputValue();
  expect(code).toMatch(/^[\w-]{43}$/);
  await page.getByRole("button", { name: "Done", exact: true }).click();
  await expect(page.getByLabel("New recovery code")).toHaveCount(0);
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await page.getByRole("link", { name: "Forgot password?" }).click();
  await page.getByRole("link", { name: "Use a recovery code" }).click();
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Recovery code").fill(code);
  await page.getByLabel("New password", { exact: true }).fill(replacement);
  await page.getByRole("button", { name: "Save new password" }).click();
  await expect(page.getByRole("status")).toContainText("Your password has been updated.");
  await page.getByRole("link", { name: "Go to sign in" }).click();
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(replacement);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Your workspace" })).toBeVisible();
});

test("a sign-in begun from verification resumes the side sheet", async ({ page }) => {
  const email = `resume-${randomUUID()}@example.test`;
  const password = `Fixture-${randomUUID()}`;
  expect((await page.request.post("/api/v1/auth/register", { data: { email, password } })).ok()).toBeTruthy();
  expect((await page.request.post("/api/v1/auth/logout", { data: {} })).ok()).toBeTruthy();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/workspace");
  await page.getByRole("button", { name: "Start a verification" }).click();
  await expect(page).toHaveURL(/next=%2Fworkspace%3Faction%3Dnew$/);
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "New verification" });
  await expect(dialog.getByLabel("Device name")).toBeFocused();
  await dialog.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(dialog).not.toBeVisible();
  await expect(page).toHaveURL(/\/workspace$/);
});

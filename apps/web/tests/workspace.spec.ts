import { expect, test } from "@playwright/test";

test("workspace search opens an example report and keeps its data separate", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Your workspace" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Example verifications" })).toBeVisible();
  await page.keyboard.press("Control+k");
  const search = page.getByRole("dialog", { name: "Search workspace" });
  const field = search.getByRole("textbox", { name: "Search verifications and tools" });
  await expect(field).toBeFocused();
  await field.fill("ThinkPad");
  await expect(search.getByRole("button", { name: /Latitude/ })).toHaveCount(0);
  await field.press("ArrowDown");
  await expect(search.getByRole("button", { name: /ThinkPad/ })).toBeFocused();
  await page.keyboard.press("Enter");
  const report = page.getByRole("dialog", { name: "ThinkPad T14 Gen 3" });
  await expect(report.getByText("SIMULATED DATA", { exact: false })).toBeVisible();
  await expect(report.getByText("1 listing difference", { exact: true })).toBeVisible();
  await expect(report.getByText("256", { exact: true })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(report).not.toBeVisible();
  await page.getByRole("button", { name: "Grid view" }).click();
  await expect(page.getByRole("button", { name: "Grid view" })).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator(".collection-grid .verification-item")).toHaveCount(2);
});

test("workspace is usable at phone width and preserves the handoff entry", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Your workspace" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Search workspace" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Handoffs", exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await page.getByRole("link", { name: /Protect a handoff/ }).click();
  await expect(page.getByRole("heading", { name: "Protect a handoff" })).toBeVisible();
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  const auth = page.getByRole("dialog", { name: "Sign in" });
  await expect(auth.getByLabel("Email")).toBeFocused();
});

import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";

test("owner records baseline, receiver accepts and return produces a signed comparison", async ({ page, browser }) => {
  await page.goto("/workspace");
  await page.getByRole("button", { name: "Create an account" }).click();
  await page.getByLabel("Email").fill("handoff-" + randomUUID() + "@example.test");
  await page.getByLabel("Password").fill("Playwright-handoff-" + randomUUID());
  await page.getByRole("button", { name: "Create account", exact: true }).click();
  await page.getByRole("link", { name: "Handoffs", exact: true }).click();
  await page.getByLabel("Asset name").fill("Loaner laptop");
  await page.getByLabel("Record type").selectOption("simulator");
  await page.getByRole("button", { name: "Create handoff" }).click();
  await page.getByRole("button", { name: "Start baseline" }).click();
  await page.getByRole("button", { name: "Record baseline" }).click();
  await page.getByRole("button", { name: "Create acceptance link" }).click();
  const link = await page.getByLabel("Private acceptance link").inputValue();
  const recipient = await browser.newPage();
  try {
    await recipient.goto(link);
    await recipient.getByRole("button", { name: "Accept handoff" }).click();
    await expect(recipient.getByText("Acceptance recorded.")).toBeVisible();
  } finally {
    await recipient.close();
  }
  await page.getByRole("button", { name: "Refresh acceptance" }).click();
  await expect(page.getByText("Receiver accepted.")).toBeVisible();
  await page.getByRole("button", { name: "Mark as handed off" }).click();
  await page.getByRole("button", { name: "Start return check" }).click();
  await page.getByRole("button", { name: "Record return" }).click();
  await expect(page.getByText("Samsung 16 GiB")).toBeVisible();
  await expect(page.getByText("Crucial 8 GiB")).toBeVisible();
  await expect(page.getByText("New scratch")).toBeVisible();
  await page.getByRole("link", { name: "Check public signature" }).click();
  await expect(page.getByRole("heading", { name: "Signature verified" })).toBeVisible();
});

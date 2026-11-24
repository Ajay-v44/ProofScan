import { expect, test } from "@playwright/test";

test("the public pitch works on phone, tablet and desktop and separates the workspace", async ({ page }) => {
  await page.goto("/home");
  for (const width of [320, 390, 768, 1440]) {
    await page.setViewportSize({ width, height: 844 });
    await expect(page.getByRole("heading", { level: 1, name: /Used tech.*Real evidence/ })).toBeVisible();
    await expect(page.getByRole("link", { name: "Explore the demo" })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
  }
  await expect(page.locator('a[href^="/admin"]')).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Your workspace" })).toHaveCount(0);
  await page.getByRole("link", { name: "Explore the demo" }).click();
  await expect(page).toHaveURL(/#demo$/);
  const tabs = page.getByRole("tablist", { name: "Report examples" });
  await expect(page.getByText("Storage differs from the listing.")).toBeVisible();
  await tabs.getByRole("tab", { name: "Before buying" }).press("ArrowRight");
  await expect(tabs.getByRole("tab", { name: "At pickup" })).toBeFocused();
  await expect(page.getByRole("tabpanel")).toContainText("The memory reading changed.");
  await tabs.getByRole("tab", { name: "At return" }).click();
  await expect(page.getByRole("tabpanel")).toContainText("One view needs a closer look.");
  await page.getByText("What does a signed report prove?", { exact: true }).click();
  await expect(page.getByText(/The signature lets you check/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "iPhone and iPad" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Android" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "macOS" })).toBeVisible();
  const collector = page.getByRole("link", { name: "Download PowerShell collector" });
  if (await collector.count()) {
    await expect(collector).toHaveAttribute("href", "/collect-windows.ps1");
    expect((await page.request.get("/collect-windows.ps1")).ok()).toBeTruthy();
  } else {
    await expect(page.getByRole("link", { name: "Download for Windows" })).toHaveAttribute("href", /^https:\/\//);
  }
  await page.getByRole("link", { name: "Open web workspace" }).click();
  await expect(page).toHaveURL(/\/workspace$/);
  await expect(page.getByRole("heading", { name: "Your workspace" })).toBeVisible();
  await expect(page.locator('a[href^="/admin"]')).toHaveCount(0);
});

test("both public routes have the same canonical and share image; operator access stays direct", async ({ page }) => {
  await page.goto("/");
  const canonical = await page.locator('link[rel="canonical"]').getAttribute("href");
  expect(canonical && new URL(canonical).pathname).toBe("/");
  await expect(page.locator('meta[name="description"]')).toHaveAttribute("content", /hardware readings and exterior photos/);
  await expect(page.locator('meta[name="twitter:card"]')).toHaveAttribute("content", "summary_large_image");
  await expect(page.locator('link[rel="manifest"]')).toHaveAttribute("href", "/manifest.webmanifest");
  const image = await page.locator('meta[property="og:image"]').getAttribute("content");
  expect(image && new URL(image).pathname).toBe("/marketing/proofscan-share.jpg");
  expect((await page.request.get("/marketing/proofscan-share.jpg")).headers()["content-type"]).toContain("image/jpeg");
  await page.goto("/home");
  await expect(page.locator('link[rel="canonical"]')).toHaveAttribute("href", canonical!);
  await expect(page.locator('meta[property="og:image"]')).toHaveAttribute("content", image!);
  const sitemap = await (await page.request.get("/sitemap.xml")).text();
  expect(sitemap).not.toContain("/admin");
  expect(sitemap).not.toContain("/workspace");
  expect((await page.request.get("/robots.txt")).ok()).toBeTruthy();
  const admin = await page.goto("/admin");
  expect(admin?.headers()["x-robots-tag"]).toContain("noindex");
  await expect(page.getByRole("heading", { name: "Operator sign-in" })).toBeVisible();
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("dialog", { name: "Sign in" }).getByLabel("Email")).toBeFocused();
});

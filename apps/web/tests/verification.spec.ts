import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { expect, test, type Browser, type Page } from "@playwright/test";

async function createVerification(buyer: Page, label: string, claims = true) {
  await buyer.goto("/workspace");
  await buyer.getByRole("link", { name: "Create an account" }).click();
  await buyer.getByLabel("Email").fill("e2e-" + randomUUID() + "@example.test");
  await buyer.getByLabel("Password", { exact: true }).fill("Local-Playwright-" + randomUUID());
  await buyer.getByRole("button", { name: "Create account", exact: true }).click();
  await buyer.getByRole("button", { name: "New verification", exact: true }).click();
  await buyer.getByLabel("Device name").fill(label);
  if (claims) {
    await buyer.getByLabel("Memory (GiB)").fill("16");
    await buyer.getByLabel("Largest drive (GB)").fill("1000");
    await buyer.getByLabel("Minimum battery health (%)").fill("85");
  }
  await buyer.getByRole("button", { name: "Create seller link" }).click();
  const input = buyer.getByLabel("Private seller link");
  await expect(input).toBeVisible();
  return input.inputValue();
}

async function openSeller(browser: Browser, link: string) {
  const context = await browser.newContext();
  const seller = await context.newPage();
  await seller.goto(link);
  await expect(seller.getByRole("button", { name: "Agree and continue" })).toBeDisabled();
  await seller.getByRole("checkbox").check();
  await seller.getByRole("button", { name: "Agree and continue" }).click();
  await expect(seller).not.toHaveURL(/#/);
  return { context, seller };
}

async function expectSignedReport(buyer: Page) {
  await buyer.getByRole("button", { name: "Done", exact: true }).click();
  await buyer.getByRole("button", { name: "Refresh" }).click();
  await buyer.getByRole("link", { name: "Open report" }).click();
  await expect(buyer.getByText("Signature verified", { exact: true })).toBeVisible();
  return buyer.getByRole("link", { name: "Open public signature check" });
}

async function exteriorPhoto(page: Page, angle: string, shade: string) {
  const jpeg = await page.evaluate(color => {
    const canvas = document.createElement("canvas");
    canvas.width = 640;
    canvas.height = 480;
    const context = canvas.getContext("2d")!;
    for (let y = 0; y < 480; y += 16) {
      for (let x = 0; x < 640; x += 16) {
        context.fillStyle = ((x + y) / 16) % 2 === 0 ? color : "#c6c6c6";
        context.fillRect(x, y, 16, 16);
      }
    }
    return canvas.toDataURL("image/jpeg").split(",")[1];
  }, shade);
  return { name: angle + ".jpg", mimeType: "image/jpeg", buffer: Buffer.from(jpeg, "base64") };
}

test("buyer receives a signed simulator report after seller consent and sharing", async ({ page: buyer, browser }) => {
  const { context, seller } = await openSeller(browser, await createVerification(buyer, "Simulator laptop"));
  try {
    await seller.getByRole("button", { name: "Use matching device" }).click();
    await expect(seller.getByText(/SIMULATED DATA ·/)).toBeVisible();
    await expect(buyer.getByRole("link", { name: "Open report" })).toHaveCount(0);
    await seller.reload();
    await expect(seller.getByRole("heading", { name: "Review before sharing" })).toBeVisible();
    await seller.getByRole("button", { name: "Share signed report" }).click();
    await expect(seller.getByRole("heading", { name: "Report shared" })).toBeVisible();
    const verify = await expectSignedReport(buyer);
    await expect(buyer.getByText(/SIMULATED DATA ·/)).toBeVisible();
    await verify.click();
    await expect(buyer.getByRole("heading", { name: "Signature verified" })).toBeVisible();
  } finally {
    await context.close();
  }
});

test("seller declines and the buyer receives no report", async ({ page: buyer, browser }) => {
  const { context, seller } = await openSeller(browser, await createVerification(buyer, "Mismatched laptop"));
  try {
    await seller.getByRole("button", { name: "Use mismatched device" }).click();
    await expect(seller.getByText("Mismatch", { exact: true })).toHaveCount(3);
    await seller.getByRole("button", { name: "Decline to share" }).click();
    await expect(seller.getByRole("heading", { name: "Sharing declined" })).toBeVisible();
    await buyer.getByRole("button", { name: "Done", exact: true }).click();
    await buyer.getByRole("button", { name: "Refresh" }).click();
    await expect(buyer.getByText("Declined", { exact: true })).toBeVisible();
    await expect(buyer.getByRole("link", { name: "Open report" })).toHaveCount(0);
    await buyer.getByRole("button", { name: "Closed", exact: true }).click();
    await expect(buyer.getByText("Declined", { exact: true })).toBeVisible();
    await buyer.getByRole("button", { name: "Shared", exact: true }).click();
    await expect(buyer.getByText("No verifications in this view")).toBeVisible();
  } finally {
    await context.close();
  }
});

test("a second device can capture exterior photos without a seller session", async ({ page: buyer, browser }) => {
  const { context, seller } = await openSeller(browser, await createVerification(buyer, "Second-camera check", false));
  const cameraContext = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  try {
    const download = seller.waitForEvent("download");
    await seller.getByRole("button", { name: "Download scan ticket" }).click();
    await download;
    await seller.getByText("Use another camera", { exact: true }).click();
    await seller.getByRole("button", { name: "Create camera link" }).click();
    const link = seller.getByRole("textbox", { name: "Camera link" });
    await expect(link).toBeVisible();
    const camera = await cameraContext.newPage();
    await camera.goto(await link.inputValue());
    await expect(camera.getByRole("heading", { name: "Photograph the device" })).toBeVisible();
    await expect(camera).not.toHaveURL(/#/);
    for (const [angle, shade] of [["front", "#494949"], ["back", "#6a6a6a"]]) {
      await expect(camera.getByRole("combobox", { name: "Photo angle" })).toHaveValue(angle);
      await camera.getByLabel("Device photo").setInputFiles(await exteriorPhoto(camera, angle, shade));
      await camera.getByRole("button", { name: "Check and save photo" }).click();
    }
    await expect(camera.getByText(/Front and back saved/)).toBeVisible();
    await expect(camera.getByRole("button", { name: "Share signed report" })).toHaveCount(0);
    await seller.getByRole("button", { name: "Refresh photos" }).click();
    await expect(seller.getByRole("link", { name: "Open front photo" })).toBeVisible();
    await expect(seller.getByRole("link", { name: "Open back photo" })).toBeVisible();
  } finally {
    await cameraContext.close();
    await context.close();
  }
});

test("a real Windows collector ticket reaches a signed buyer report", async ({ page: buyer, browser }, info) => {
  test.skip(process.platform !== "win32" || process.env.PROOFSCAN_REAL_WINDOWS !== "1", "Run on a Windows host with CIM access.");
  const { context, seller } = await openSeller(browser, await createVerification(buyer, "Windows hardware check", false));
  try {
    const download = seller.waitForEvent("download");
    await seller.getByRole("button", { name: "Download scan ticket" }).click();
    const ticket = await (await download).path();
    expect(ticket).toBeTruthy();
    const output = info.outputPath("windows-evidence.json");
    const collector = resolve("public/collect-windows.ps1");
    mkdirSync(dirname(output), { recursive: true });
    const powershell = process.env.PROOFSCAN_POWERSHELL ?? "pwsh.exe";
    execFileSync(powershell, ["-NoProfile", "-NonInteractive", "-File", collector, "-TicketFile", ticket!, "-OutputFile", output], { timeout: 45_000 });
    for (const [angle, shade] of [["front", "#494949"], ["back", "#6a6a6a"]]) {
      await seller.getByRole("combobox", { name: "Photo angle" }).selectOption(angle);
      await seller.getByLabel("Device photo").setInputFiles(await exteriorPhoto(seller, angle, shade));
      await seller.getByRole("button", { name: "Check and save photo" }).click();
      await expect(seller.getByRole("link", { name: "Open " + angle + " photo" })).toBeVisible();
    }
    await seller.getByText("Check the display, keyboard and speakers", { exact: true }).click();
    await seller.getByLabel("Display result").selectOption("PASS");
    await seller.getByLabel("Windows scan file").setInputFiles(output);
    await seller.getByRole("button", { name: "Preview scan" }).click();
    await expect(seller.getByText(/Windows collector reading/)).toBeVisible();
    await expect(seller.getByRole("link", { name: "Open front photo" })).toBeVisible();
    await expect(seller.getByText("Seller observation", { exact: true })).toBeVisible();
    await seller.getByRole("button", { name: "Share signed report" }).click();
    await expect(seller.getByRole("heading", { name: "Report shared" })).toBeVisible();
    await expectSignedReport(buyer);
    await expect(buyer.getByText(/Windows collector reading/)).toBeVisible();
    const photoLink = await buyer.getByRole("link", { name: "Open front photo" }).getAttribute("href");
    expect((await buyer.request.get(photoLink!)).headers()["content-type"]).toBe("image/jpeg");
    await buyer.getByRole("button", { name: "Create pickup recheck link" }).click();
    await expect(buyer.getByLabel("Private pickup link")).toBeVisible();
    await buyer.goto("/advisor");
    await buyer.getByLabel("Ask ProofScan").fill("Compare my verified devices by memory.");
    await buyer.getByRole("button", { name: "Send message" }).click();
    await expect(buyer.getByRole("link", { name: "Open signed report" })).toBeVisible();
  } finally {
    await context.close();
  }
});

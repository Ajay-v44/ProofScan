const assert = require("node:assert/strict");
const test = require("node:test");
const profiles = require("../eas.json").build;
const { isWorkspaceUrl, parseOrigin, parsePublicPage } = require("../src/origin.cjs");

test("release builds require a plain HTTPS workspace origin", () => {
  assert.equal(parseOrigin("https://proofscan.example/"), "https://proofscan.example");
  assert.equal(parseOrigin("http://192.168.1.2:3000", true), "http://192.168.1.2:3000");

  for (const value of [
    undefined, "http://proofscan.example", "https://", "https:proofscan.example",
    "https://proofscan.example/path", "https://proofscan.example/?", "https://proofscan.example/#",
    "https://name:password@proofscan.example", "https://proofscan.example/../",
  ]) {
    assert.throws(() => parseOrigin(value));
  }
});

test("workspace navigation stays on the configured HTTP or HTTPS origin", () => {
  const origin = "https://proofscan.example";
  assert.equal(isWorkspaceUrl(origin + "/reports/example", origin), true);
  assert.equal(isWorkspaceUrl(origin + ":443/sign-in", origin), true);
  for (const value of [
    "http://proofscan.example", "https://proofscan.example:8080", "https://proofscan.example.other.example",
    "https://proofscan.example@other.example", "https://name@proofscan.example",
    "blob:https://proofscan.example/id", "proofscan://seller", "file:///test", "/reports/example",
  ]) {
    assert.equal(isWorkspaceUrl(value, origin), false, value);
  }
});

test("privacy and account deletion links accept only HTTPS pages without tokens", () => {
  const key = "EXPO_PUBLIC_PROOFSCAN_PRIVACY_URL";
  assert.equal(parsePublicPage("https://proofscan.example/privacy", key), "https://proofscan.example/privacy");
  for (const value of [
    undefined, "http://proofscan.example/privacy", "https:proofscan.example/privacy",
    "https://name@proofscan.example/privacy", "https://proofscan.example/privacy?token=test",
    "https://proofscan.example/privacy#test",
  ]) {
    assert.throws(() => parsePublicPage(value, key), new RegExp(key));
  }
});

test("release and preview profiles enforce public release configuration", () => {
  assert.equal(profiles.development.developmentClient, true);
  assert.equal(profiles.preview.distribution, "internal");
  assert.equal(profiles.preview.android.buildType, "apk");
  assert.equal(profiles.production.distribution, "store");
  assert.equal(profiles.production.android.buildType, "app-bundle");
  assert.equal(profiles.production.autoIncrement, true);
  for (const name of ["preview", "production"]) {
    assert.equal(profiles[name].environment, name);
    assert.equal(profiles[name].env.PROOFSCAN_REQUIRE_HTTPS_ORIGIN, "1");
  }
});

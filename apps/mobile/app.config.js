const { parseOrigin, parsePublicPage } = require("./src/origin.cjs");

module.exports = ({ config }) => {
  if (process.env.PROOFSCAN_REQUIRE_HTTPS_ORIGIN === "1") {
    parseOrigin(process.env.EXPO_PUBLIC_PROOFSCAN_ORIGIN);
    parsePublicPage(process.env.EXPO_PUBLIC_PROOFSCAN_PRIVACY_URL, "EXPO_PUBLIC_PROOFSCAN_PRIVACY_URL");
    parsePublicPage(process.env.EXPO_PUBLIC_PROOFSCAN_DELETE_ACCOUNT_URL, "EXPO_PUBLIC_PROOFSCAN_DELETE_ACCOUNT_URL");
    config.android = {
      ...config.android,
      blockedPermissions: [...(config.android?.blockedPermissions ?? []), "android.permission.SYSTEM_ALERT_WINDOW"],
    };
  }
  return config;
};

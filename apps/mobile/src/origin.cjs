/**
 * @param {string | undefined} raw
 * @param {boolean} [allowHttp]
 */
function parseOrigin(raw, allowHttp = false) {
  if (!raw) throw new Error("Set EXPO_PUBLIC_PROOFSCAN_ORIGIN to your ProofScan server origin.");
  const source = raw.trim();
  let url;
  try {
    url = new URL(source);
  } catch {
    throw new Error("The ProofScan server origin is invalid.");
  }
  const secure = url.protocol === "https:" || (allowHttp && url.protocol === "http:");
  if (!secure) throw new Error("The ProofScan server must use HTTPS.");
  if (!/^https?:\/\/[^/?#\\@\s]+\/?$/i.test(source) || url.href !== url.origin + "/") {
    throw new Error("Use the ProofScan server origin without a path, query, fragment, or credentials.");
  }
  return url.origin;
}

/**
 * @param {string} value
 * @param {string} origin
 */
function isWorkspaceUrl(value, origin) {
  try {
    const url = new URL(value);
    return url.origin === origin && url.protocol === new URL(origin).protocol && !url.username && !url.password;
  } catch {
    return false;
  }
}

/**
 * @param {string | undefined} raw
 * @param {string} variable
 */
function parsePublicPage(raw, variable) {
  const source = raw?.trim() ?? "";
  try {
    const url = new URL(source);
    if (/^https:\/\/[^/?#\\@\s]+(?:\/[^?#\\\s]*)?$/i.test(source) && !url.username && !url.password) return url.href;
  } catch {
    // A missing or malformed URL must never reach the system browser.
  }
  throw new Error("Set " + variable + " to a public HTTPS page.");
}

module.exports = { parseOrigin, isWorkspaceUrl, parsePublicPage };

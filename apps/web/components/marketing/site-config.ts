import type { Metadata } from "next";

function configuredUrl(name: string, originOnly = false): URL | undefined {
  const value = process.env[name]?.trim();
  if (!value) return;

  let url: URL;
  try { url = new URL(value); }
  catch { throw new Error(name + " must be an absolute URL."); }

  const localOrigin = originOnly && url.protocol === "http:" && ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname);
  if ((url.protocol !== "https:" && !localOrigin) || url.username || url.password ||
    (originOnly && (url.pathname !== "/" || url.search || url.hash))) {
    throw new Error(name + (originOnly ? " must be a plain HTTPS origin or a local development origin." : " must be an HTTPS URL without credentials."));
  }
  return url;
}

export const siteOrigin = configuredUrl("PROOFSCAN_SITE_URL", true) ?? new URL("http://localhost:3000");
export const isPublicSite = siteOrigin.protocol === "https:";
export const pitchTitle = "Used device verification for buyers and sellers";
export const pitchDescription = "Check used phones and laptops before you pay. ProofScan puts available hardware readings and exterior photos in a signed report you can compare again at pickup.";

export const downloadUrls = {
  windows: configuredUrl("PROOFSCAN_WINDOWS_DOWNLOAD_URL")?.href,
  mac: configuredUrl("PROOFSCAN_MACOS_DOWNLOAD_URL")?.href,
  android: configuredUrl("PROOFSCAN_ANDROID_DOWNLOAD_URL")?.href,
  ios: configuredUrl("PROOFSCAN_IOS_DOWNLOAD_URL")?.href,
};

const shareImage = { url: "/marketing/proofscan-share.jpg", width: 1200, height: 630, alt: "ProofScan. Used tech. Real evidence." };

export const pitchMetadata: Metadata = {
  title: pitchTitle,
  description: pitchDescription,
  alternates: { canonical: "/" },
  robots: { index: isPublicSite, follow: isPublicSite },
  openGraph: { type: "website", siteName: "ProofScan", title: "ProofScan · " + pitchTitle, description: pitchDescription,
    url: "/", locale: "en_US", images: [shareImage] },
  twitter: { card: "summary_large_image", title: "ProofScan · " + pitchTitle, description: pitchDescription, images: [shareImage] },
};

export const siteSchema = {
  "@context": "https://schema.org",
  "@graph": [
    { "@type": "WebSite", "@id": siteOrigin.href + "#website", name: "ProofScan", url: siteOrigin.href, inLanguage: "en" },
    { "@type": "SoftwareApplication", "@id": siteOrigin.href + "#application", name: "ProofScan", url: siteOrigin.href,
      applicationCategory: "UtilitiesApplication", description: pitchDescription,
      operatingSystem: "Web, Windows, macOS, Android, iOS", image: new URL(shareImage.url, siteOrigin).href },
  ],
};

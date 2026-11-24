import "@fontsource-variable/manrope";
import { themeVariables } from "@proofscan/design-tokens";
import type { Metadata, Viewport } from "next";
import type { CSSProperties } from "react";
import { Providers } from "../components/providers";
import { isPublicSite, siteOrigin } from "../components/marketing/site-config";
import "./styles.css";

export const metadata: Metadata = {
  metadataBase: siteOrigin,
  applicationName: "ProofScan",
  title: { default: "ProofScan", template: "%s · ProofScan" },
  description: "Check device readings and condition before you buy, sell, or hand over a device.",
  robots: { index: isPublicSite, follow: isPublicSite },
};

export const viewport: Viewport = { themeColor: "#101e2c" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en" style={themeVariables as CSSProperties}><body><Providers>{children}</Providers></body></html>;
}

import "@fontsource-variable/manrope";
import { themeVariables } from "@proofscan/design-tokens";
import type { Metadata } from "next";
import type { CSSProperties } from "react";
import { Providers } from "../components/providers";
import "./styles.css";

export const metadata: Metadata = {
  title: { default: "ProofScan", template: "%s · ProofScan" },
  description: "Check device readings and condition before you buy, sell, or hand over a device.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en" style={themeVariables as CSSProperties}><body><Providers>{children}</Providers></body></html>;
}

import "@fontsource-variable/manrope";
import { themeVariables } from "@proofscan/design-tokens";
import type { Metadata } from "next";
import type { CSSProperties } from "react";
import { Providers } from "../components/providers";
import "./styles.css";

export const metadata: Metadata = { title: "ProofScan", description: "Verify what it is. Verify what changed." };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en" style={themeVariables as CSSProperties}><body><Providers>{children}</Providers></body></html>;
}

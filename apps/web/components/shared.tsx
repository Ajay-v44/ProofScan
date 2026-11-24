import { CircleAlert, LayoutGrid, ShieldCheck } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import type { ReactNode } from "react";
import { version } from "../package.json";

export function Brand() {
  return <Link href="/" className="brand"><Image src="/brand/proofscan-mark.webp" width={36} height={36} alt="" className="brand-mark" unoptimized />ProofScan</Link>;
}

export function ProductFooter() {
  return <footer className="product-footer"><nav aria-label="Product information">
    <Link href="/about">About ProofScan</Link><Link href="/help">Help</Link><Link href="/privacy">Privacy</Link>
  </nav><span>Web version {version}</span></footer>;
}

export function PublicShell({ children, wide = false, isGuest = false }: { children: ReactNode; wide?: boolean; isGuest?: boolean }) {
  return <div className="public-shell">
    <a className="skip-link" href="#main">Skip to content</a>
    <header className="public-head"><div className="public-head-inner"><Brand /><nav className="public-navigation" aria-label="ProofScan">
      {isGuest ? <Link className="nav-link" href="/help">Help</Link> : <>
      <Link className="nav-link" href="/"><LayoutGrid size={17} aria-hidden />Workspace</Link>
      <Link className="nav-link" href="/verify"><ShieldCheck size={17} aria-hidden />Check a report</Link>
      </>}
    </nav></div></header>
    <main id="main" tabIndex={-1} className={"public-main" + (wide ? " public-wide" : "")}>{children}</main>
    <ProductFooter />
  </div>;
}

export function Status({ value }: { value: string }) {
  const labels: Record<string, string> = {
    DRAFT: "Draft", LINK_CREATED: "Awaiting seller", SELLER_OPENED: "Seller opened", CONSENTED: "Consented",
    SCANNING: "Scan in progress", REPORT_READY: "Preview ready", SELLER_REVIEW: "Seller reviewing",
    SHARED: "Shared", COMPLETED: "Report shared", DECLINED: "Declined", CANCELLED: "Cancelled",
    EXPIRED: "Expired", FAILED: "Failed", MATCH: "Match", MISMATCH: "Mismatch", UNAVAILABLE: "Unavailable",
  };
  return <span className={"status " + (["COMPLETED", "MATCH", "SHARED"].includes(value) ? "good"
    : ["DECLINED", "FAILED", "MISMATCH"].includes(value) ? "warning" : "")}>{labels[value] ?? value}</span>;
}

export function ErrorNote({ error }: { error: unknown }) {
  if (!error) return null;
  return <p role="alert" className="notice error"><CircleAlert size={17} aria-hidden />{error instanceof Error ? error.message : "Something went wrong."}</p>;
}

export function PrivacyNote() {
  return <span className="privacy-note"><ShieldCheck size={15} aria-hidden /> Seller controls what is shared</span>;
}

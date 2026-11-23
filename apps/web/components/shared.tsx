import { CircleAlert, LayoutGrid, ScanLine, ShieldCheck } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

export function Brand() {
  return <Link href="/" className="brand"><span className="brand-mark"><ScanLine aria-hidden size={24} /></span>ProofScan</Link>;
}

export function PublicShell({ children, wide = false }: { children: ReactNode; wide?: boolean }) {
  return <div className="public-shell">
    <a className="skip-link" href="#main">Skip to content</a>
    <header className="public-head"><Brand /><nav className="public-navigation" aria-label="ProofScan">
      <Link className="nav-link" href="/"><LayoutGrid size={17} aria-hidden />Workspace</Link>
      <Link className="nav-link" href="/verify"><ShieldCheck size={17} aria-hidden />Check a report</Link>
    </nav></header>
    <main id="main" className={"public-main" + (wide ? " public-wide" : "")}>{children}</main>
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

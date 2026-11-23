"use client";

import { api, type SignedReport, type VerificationResult } from "@proofscan/api-client";
import { useQuery } from "@tanstack/react-query";
import { FileCheck2, ShieldCheck, ShieldX } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ReportDetails } from "./report";
import { ErrorNote, PublicShell } from "./shared";
import { Button } from "./ui/button";

export function BuyerReport({ id }: { id: string }) {
  const report = useQuery({ queryKey: ["report", id], queryFn: () => api<SignedReport>("/verifications/" + id + "/report") });
  return <PublicShell><div className="page-title"><span className="eyebrow"><FileCheck2 size={16} aria-hidden /> Purchase report</span><h1>{report.data?.payload.label ?? "Device verification report"}</h1></div>
    <ErrorNote error={report.error} />
    {report.isPending && <p role="status">Loading report…</p>}
    {report.data && <section className="panel form">
      <div><h2>Verification results</h2><p>Recorded {new Date(report.data.payload.captured_at).toLocaleString()}</p></div>
      <p className={report.data.valid ? "notice good" : "notice warning"}>{report.data.valid ? "Signature verified" : "This signature is no longer valid"}</p>
      <ReportDetails report={report.data.payload} photoPath={"/verifications/" + id + "/photos"} />
      <Link className="quiet-link" href={"/verify/" + report.data.payload.report_id}>Open public signature check</Link>
    </section>}
  </PublicShell>;
}

export function VerifyReport({ id }: { id?: string }) {
  const router = useRouter();
  const result = useQuery({ queryKey: ["verify", id], enabled: !!id, staleTime: 0, queryFn: () => api<VerificationResult>("/reports/" + id + "/verify") });
  return <PublicShell><div className="page-title"><span className="eyebrow"><ShieldCheck size={16} aria-hidden /> Report integrity</span><h1>Check a report</h1><p>Look up a report ID to check its signature and current validity.</p></div>
    <form className="panel form" key={id ?? "lookup"} onSubmit={event => {
      event.preventDefault();
      const value = String(new FormData(event.currentTarget).get("report") ?? "").trim();
      if (value === id) void result.refetch();
      else router.push("/verify/" + encodeURIComponent(value));
    }}>
      <label>Report ID<input name="report" defaultValue={id} placeholder="Paste the report ID" required pattern="[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}" /></label>
      <Button type="submit">Check signature</Button>
    </form>
    <ErrorNote error={result.error} />
    {id && result.isPending && <p role="status">Checking signature…</p>}
    {result.data && <section className="panel form">
      <div className={"icon-tile " + (result.data.valid ? "mint" : "clay")}>{result.data.valid ? <ShieldCheck size={24} aria-hidden /> : <ShieldX size={24} aria-hidden />}</div>
      <div><h2>{result.data.valid ? "Signature verified" : result.data.invalidated ? "Report invalidated" : "Signature could not be verified"}</h2>
        <p>This check covers the integrity and current validity of the signed report. The buyer keeps the detailed readings private.</p></div>
      <details><summary>Technical details</summary><dl className="technical"><dt>Report ID</dt><dd>{result.data.report_id}</dd><dt>Key</dt><dd>{result.data.key_id}</dd><dt>SHA-256</dt><dd>{result.data.digest}</dd><dt>Ed25519 signature</dt><dd>{result.data.signature}</dd></dl></details>
    </section>}
  </PublicShell>;
}

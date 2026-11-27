"use client";

import { api, type SignedReport, type VerificationResult } from "@proofscan/api-client";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ShieldCheck, ShieldX } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ReportDetails } from "./report";
import { EvidenceGallery } from "./evidence-gallery";
import { angleName } from "./photo-capture";
import { ErrorNote, PublicShell } from "./shared";
import { WorkspaceFrame } from "./workspace-frame";
import { Button } from "./ui/button";

export function BuyerReport({ id }: { id: string }) {
  const report = useQuery({ queryKey: ["report", id], queryFn: () => api<SignedReport>("/verifications/" + id + "/report") });
  const recheck = useMutation({
    mutationFn: () => api<{ guest_url: string }>("/verifications/" + id + "/recheck", {}),
  });
  const payload = report.data?.payload;
  const pickup = payload?.pickup;
  const baselineId = pickup?.baseline_verification_id;
  const baseline = useQuery({
    queryKey: ["report", baselineId],
    enabled: Boolean(baselineId) && report.data?.baseline_valid !== false,
    queryFn: () => api<SignedReport>("/verifications/" + baselineId + "/report"),
  });
  return <WorkspaceFrame page="Purchase report"><div className="page-title"><h1>{report.data?.payload.label ?? "Device verification report"}</h1>
    {payload && <p>Captured {new Date(payload.captured_at).toLocaleString()}</p>}</div>
    <ErrorNote error={report.error} />
    {report.isPending && <p role="status">Loading report…</p>}
    {report.data && <div className="report-layout"><section className="panel form">
      <h2>Verification results</h2>
      <ReportDetails report={report.data.payload} photoPath={"/verifications/" + id + "/photos"} />
      {pickup && <section className="flow-section">
        <h3>Pickup comparison</h3>
        <Link href={"/reports/" + pickup.baseline_verification_id}>Open the original signed report</Link>
        {report.data.baseline_valid === false && <p className="notice warning">The original report is no longer valid. Review the new scan on its own.</p>}
        <p>{pickup.changed_hardware.length
          ? "Hardware differences to inspect: " + pickup.changed_hardware.join(", ")
          : "No differences in the hardware fields available in both reports."}</p>
        <div className="comparison-views">{pickup.visuals.map(view => {
          const before = baseline.data?.payload.visual_evidence?.find(photo => photo.angle === view.angle);
          const after = payload?.visual_evidence?.find(photo => photo.angle === view.angle);
          return <div key={view.angle}><h4>{angleName[view.angle]}</h4><p>{view.detail}</p>
            <EvidenceGallery thumbnails items={[
              ...(before ? [{ href: "/api/v1/verifications/" + baselineId + "/photos/" + before.id, label: "Original " + view.angle + " view" }] : []),
              ...(after ? [{ href: "/api/v1/verifications/" + id + "/photos/" + after.id, label: "Pickup " + view.angle + " view" }] : []),
            ]} />
          </div>;
        })}</div>
        <p>Check the item in person. Matching readings and photos cannot establish that it is the same physical unit.</p>
      </section>}
    </section><aside className="report-actions">
      <section className="panel form">
        <h2>Report signature</h2>
        <p className={report.data.valid ? "notice good" : "notice warning"}>{report.data.valid ? "Signature verified" : "This signature is no longer valid"}</p>
        <Link className="quiet-link" href={"/verify/" + report.data.payload.report_id}>Open public signature check</Link>
      </section>
      {report.data.valid && report.data.payload.assurance === "COLLECTOR_REPORTED" && <section className="panel form">
        <h2>Check the device at pickup</h2>
        <p>When you have the device in hand, collect fresh readings and photos using a private recheck link. The new report compares them with this one.</p>
        {!recheck.data && <Button variant="outline" disabled={recheck.isPending} onClick={() => recheck.mutate()}>Create pickup recheck link</Button>}
        {recheck.data && <label>Private pickup link<input readOnly value={recheck.data.guest_url} onFocus={event => event.currentTarget.select()} /></label>}
        <ErrorNote error={recheck.error} />
      </section>}
    </aside></div>}
  </WorkspaceFrame>;
}

export function VerifyReport({ id }: { id?: string }) {
  const router = useRouter();
  const result = useQuery({ queryKey: ["verify", id], enabled: !!id, staleTime: 0, queryFn: () => api<VerificationResult>("/reports/" + id + "/verify") });
  return <PublicShell wide><div className="signature-lookup">
    <section className="panel form signature-panel">
      <div className="page-title"><span className="icon-tile mint"><ShieldCheck size={21} aria-hidden /></span>
        <h1>Check a report</h1><p>Look up a report ID to check its signature and current validity.</p></div>
      <form className="form" key={id ?? "lookup"} onSubmit={event => {
      event.preventDefault();
      const value = String(new FormData(event.currentTarget).get("report") ?? "").trim();
      if (value === id) void result.refetch();
      else router.push("/verify/" + encodeURIComponent(value));
    }}>
      <label>Report ID<input name="report" defaultValue={id} placeholder="Paste the report ID" required pattern="[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}" /></label>
        <Button type="submit" disabled={result.isFetching}>{result.isFetching ? "Checking…" : "Check signature"}</Button>
      </form>
      <ErrorNote error={result.error} />
    </section>
    <aside className="panel signature-help">
      <Image src="/workspace/verify.webp" width={840} height={560} alt="" unoptimized />
      <div><h2>Where to find the ID</h2><p>Open the signed report shared with you and copy its report ID from the signature section.</p></div>
    </aside>
    </div>
    {id && result.isPending && <p role="status">Checking signature…</p>}
    {result.data && <section className="panel form">
      <div className={"icon-tile " + (result.data.valid ? "mint" : "clay")}>{result.data.valid ? <ShieldCheck size={24} aria-hidden /> : <ShieldX size={24} aria-hidden />}</div>
      <div><h2>{result.data.valid ? "Signature verified" : result.data.invalidated ? "Report invalidated" : "Signature could not be verified"}</h2>
        <p>This check covers the integrity and current validity of the signed report. The buyer keeps the detailed readings private.</p></div>
      <details><summary>Technical details</summary><dl className="technical"><dt>Report ID</dt><dd>{result.data.report_id}</dd><dt>Key</dt><dd>{result.data.key_id}</dd><dt>SHA-256</dt><dd>{result.data.digest}</dd><dt>Ed25519 signature</dt><dd>{result.data.signature}</dd></dl></details>
    </section>}
  </PublicShell>;
}

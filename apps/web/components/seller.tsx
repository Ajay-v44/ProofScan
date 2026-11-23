"use client";

import { api, type FunctionalCheck, type GuestView, type ScanTicket } from "@proofscan/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Download, Laptop2, LockKeyhole, ScanLine, Upload } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { ReportDetails } from "./report";
import { PhotoCapture } from "./photo-capture";
import { FunctionalChecks } from "./functional-checks";
import { ErrorNote, PublicShell, Status } from "./shared";
import { Button, buttonVariants } from "./ui/button";

export function downloadTicket(ticket: ScanTicket) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(ticket)], { type: "application/json" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = "proofscan-ticket.json";
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function Seller({ id }: { id: string }) {
  const path = "/guest/" + id;
  const client = useQueryClient();
  const key = ["seller", id];
  const [accepted, setAccepted] = useState(false);
  const [ticket, setTicket] = useState<ScanTicket | null>(null);
  const [desktop, setDesktop] = useState<"windows" | "macos">("windows");
  const [file, setFile] = useState<File | null>(null);
  const [checks, setChecks] = useState<FunctionalCheck[]>([]);

  const guest = useQuery({
    queryKey: key,
    queryFn: async () => {
      const token = window.location.hash.slice(1);
      if (!token) return api<GuestView>(path);
      const next = await api<GuestView>(path + "/exchange", { token });
      window.history.replaceState(null, "", window.location.pathname + window.location.search);
      return next;
    },
  });
  const save = (view: GuestView) => client.setQueryData(key, view);
  const consent = useMutation({ mutationFn: () => api<GuestView>(path + "/consent", { policy_version: "2026-11-23", accepted: true }), onSuccess: save });
  const windows = useMutation({
    mutationFn: () => api<ScanTicket>(path + "/scan", { platform: desktop }),
    onSuccess: next => { setTicket(next); setFile(null); downloadTicket(next); },
  });
  const simulate = useMutation({
    mutationFn: async (fixture: "verified" | "misrepresented") => {
      const scan = await api<ScanTicket>(path + "/scan", { platform: "simulator" });
      return api<GuestView>(path + "/submit", { scan_id: scan.scan_id, challenge: scan.challenge, platform: "simulator", fixture });
    },
    onSuccess: save,
  });
  const upload = useMutation({
    mutationFn: async (scanFile: File) => {
      if (scanFile.size > 65_536) throw new Error("This scan file is too large.");
      let evidence: unknown;
      try { evidence = JSON.parse(await scanFile.text()); }
      catch { throw new Error("Choose the scan JSON file exported by the desktop collector."); }
      if (typeof evidence !== "object" || evidence === null || !("platform" in evidence) || evidence.platform !== desktop) {
        throw new Error("Choose a scan file that matches the selected platform.");
      }
      return api<GuestView>(path + "/submit", { ...evidence, functional: checks });
    },
    onSuccess: save,
  });
  const decision = useMutation({
    mutationFn: (choice: "share" | "decline") => api<GuestView>(path + "/decision", { decision: choice }),
    onSuccess: save,
  });
  const status = guest.data?.verification.status;
  const busy = consent.isPending || windows.isPending || simulate.isPending || upload.isPending || decision.isPending;
  const scanning = status === "CONSENTED" || status === "SCANNING";
  const steps = ["Consent", "Collect", "Review", "Decision"];
  const step = status === "COMPLETED" || status === "DECLINED" ? 3 : status === "SELLER_REVIEW" ? 2 : scanning ? 1 : 0;

  const claims = guest.data?.claims;
  const advertised = [
    { label: "Memory", value: claims?.memory_gib, unit: " GiB" },
    { label: "Largest drive", value: claims?.storage_gb, unit: " GB" },
    { label: "Minimum battery health", value: claims?.battery_percent, unit: "%" },
  ].filter(item => item.value != null);

  return <PublicShell wide>
    <div className="page-title"><span className="eyebrow"><LockKeyhole aria-hidden size={15} /> Private seller session</span>
      <h1>{guest.data?.verification.label ?? "Device verification"}</h1>
    </div>
    {guest.isPending && <p className="notice" role="status">Opening seller session…</p>}
    <ErrorNote error={guest.error ?? consent.error ?? windows.error ?? simulate.error ?? upload.error ?? decision.error} />
    {guest.data && <>
      <ol className="steps" aria-label="Verification progress">{steps.map((name, i) => <li key={name} aria-current={step === i ? "step" : undefined} className={step >= i ? "reached" : ""}><span>{i + 1}</span>{name}</li>)}</ol>
      <div className="flow-grid">
        <div className="flow-content">
      {status === "SELLER_OPENED" && <section className="panel form">
        <div className="icon-tile mint"><LockKeyhole size={22} aria-hidden /></div>
        <div><h2>Review what we collect</h2><p>The collector reads device information such as model, processor and memory. You can also add photos of the device exterior.</p></div>
        <label className="checkbox"><input type="checkbox" checked={accepted} onChange={event => setAccepted(event.target.checked)} />I agree to collect these hardware readings for this verification.</label>
        <Button onClick={() => consent.mutate()} disabled={!accepted || busy}>Agree and continue</Button>
      </section>}
      {scanning && <section className="panel form">
        <div className="icon-tile mint"><Laptop2 size={22} aria-hidden /></div>
        <div><h2>Collect desktop readings</h2><p>Use the device you are selling. The scan ticket expires after 15 minutes. For Android and iOS, open the original seller link in the mobile scanner.</p></div>
        <div className="flow-section">
        <label>Desktop platform<select value={desktop} onChange={event => {
          setDesktop(event.target.value as "windows" | "macos");
          setTicket(null);
          setFile(null);
        }}><option value="windows">Windows</option><option value="macos">macOS</option></select></label>
        <div className="actions"><Button onClick={() => windows.mutate()} disabled={busy}><Download size={17} aria-hidden />{ticket ? "Download a fresh ticket" : "Download scan ticket"}</Button>
          {desktop === "windows" && <a className={buttonVariants({ variant: "outline" })} href="/collect-windows.ps1" download><Download size={17} aria-hidden />PowerShell collector</a>}</div>
        <details><summary>Run the collector</summary>
          <p>Open the ProofScan desktop app, load the ticket and export a scan.</p>
          {desktop === "windows" && <><p>To use the script, review it and then run this command in PowerShell from your downloads folder.</p>
            <pre>./collect-windows.ps1 -TicketFile ./proofscan-ticket.json -OutputFile ./proofscan-scan.json</pre></>}
        </details>
        </div>
        <div className="flow-section">
          <h3>Optional checks</h3>
          {ticket && <PhotoCapture path={path} ticket={ticket} photos={guest.data.photos} onSaved={() => client.invalidateQueries({ queryKey: key })} />}
          <FunctionalChecks checks={checks} onChange={setChecks} />
        </div>
        <form className="form" onSubmit={event => { event.preventDefault(); if (file) upload.mutate(file); }}>
          <label>{desktop === "windows" ? "Windows" : "macOS"} scan file<input key={desktop + (ticket?.challenge ?? "restored")} type="file" accept=".json,application/json" onChange={event => setFile(event.target.files?.[0] ?? null)} required /></label>
          <Button type="submit" variant="outline" disabled={!file || busy}><Upload size={17} aria-hidden />Preview scan</Button>
        </form>
        {guest.data.simulator_enabled && <div className="simulator"><strong>Simulator</strong><p>These fixtures produce a report marked SIMULATED DATA.</p>
          <div className="actions"><Button variant="outline" disabled={busy} onClick={() => simulate.mutate("verified")}>Use matching device</Button><Button variant="outline" disabled={busy} onClick={() => simulate.mutate("misrepresented")}>Use mismatched device</Button></div>
        </div>}
      </section>}
      {status === "SELLER_REVIEW" && guest.data.preview && <section className="panel form">
        <div><h2>Review before sharing</h2><p>The buyer can view these readings only if you choose to share them.</p></div>
        <ReportDetails report={guest.data.preview} photoPath={path + "/photos"} />
        <div className="actions"><Button disabled={busy} onClick={() => decision.mutate("share")}>Share signed report</Button><Button variant="outline" disabled={busy} onClick={() => decision.mutate("decline")}>Decline to share</Button></div>
      </section>}
      {status === "COMPLETED" && <section className="panel form"><div className="icon-tile mint"><CheckCircle2 size={24} aria-hidden /></div><div><h2>Report shared</h2><p>The buyer can open the signed report from their workspace.</p></div>
        {guest.data.report_id && <Link className="quiet-link" href={"/verify/" + guest.data.report_id}>Check report signature</Link>}</section>}
      {status === "DECLINED" && <section className="panel form"><span className="icon-tile"><ScanLine size={24} aria-hidden /></span><div><h2>Sharing declined</h2><p>The buyer received your decision. Your scan details stayed private.</p></div><Status value={status} /></section>}
        </div>
        <aside className="flow-aside">
          {advertised.length > 0 && <section className="panel"><h2>From the listing</h2>
            <dl className="flow-claims">{advertised.map(item => <div key={item.label}><dt>{item.label}</dt><dd>{item.value}{item.unit}</dd></div>)}</dl>
          </section>}
          <section className="panel"><span className="icon-tile mint"><LockKeyhole size={19} aria-hidden /></span>
            <h2>Sharing is your choice</h2><p>Only you can see the preview. The buyer sees the readings and any photos you include after you choose to share.</p>
          </section>
        </aside>
      </div>
    </>}
  </PublicShell>;
}

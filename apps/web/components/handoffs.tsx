"use client";

import { api, ApiError, type Angle, type Handoff, type HandoffMode, type HandoffReport, type ScanTicket } from "@proofscan/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ErrorNote, PublicShell, Status } from "./shared";
import { WorkspaceFrame } from "./workspace-frame";
import { downloadTicket } from "./seller";
import { angleName, jpeg, views } from "./photo-capture";
import { CameraPicker } from "./camera-picker";
import { EvidenceGallery } from "./evidence-gallery";
import { LoadMore, useOwnerCollection } from "./owner-collection";
import { accountHref } from "./account-navigation";
import { Button, buttonVariants } from "./ui/button";

const conditionLabels: Record<string, string> = { clean: "No visible damage", visible_wear: "Visible wear", damaged: "Visible damage" };
const handoffLabels: Record<string, string> = {
  DRAFT: "Draft", BASELINE_SCANNING: "Baseline in progress", BASELINE_CREATED: "Baseline saved",
  ACTIVE_HANDOFF: "Handed off", RETURN_SCANNING: "Return check in progress", REPORT_READY: "Comparison ready", CLOSED: "Closed",
};

export function HandoffList() {
  const router = useRouter();
  const client = useQueryClient();
  const session = useQuery({
    queryKey: ["session"], queryFn: () => api<{ user_id: string; simulator_enabled: boolean }>("/auth/session"),
  });
  const list = useOwnerCollection<Handoff>("/handoffs", "handoffs", session.data?.user_id);
  const create = useMutation({
    mutationFn: (body: { label: string; mode: HandoffMode }) => api<Handoff>("/handoffs", body),
    onSuccess: item => { void client.invalidateQueries({ queryKey: ["handoffs"] }); router.push("/handoffs/" + item.id); },
  });
  const needsAccount = session.error instanceof ApiError && session.error.status === 401;
  return <WorkspaceFrame page="Handoffs">
    <div className="page-title"><h1>Protect a handoff</h1>
      <p>Record the condition before an item leaves, then check what changed when it comes back.</p></div>
    <ErrorNote error={(needsAccount ? null : session.error) ?? list.error ?? create.error} />
    {needsAccount && <section className="panel form"><h2>Start a new handoff</h2>
      <p>Sign in to save the starting condition and return to it when the item comes back.</p>
      <Link className={buttonVariants()} href={accountHref("sign-in", "/handoffs")}>Sign in</Link>
    </section>}
    {session.data && <div className="handoff-library"><form className="panel form" onSubmit={event => {
      event.preventDefault();
      const data = new FormData(event.currentTarget);
      create.mutate({ label: String(data.get("label")), mode: String(data.get("mode")) as HandoffMode });
    }}>
      <h2>Start a new handoff</h2>
      <label>Asset name<input name="label" maxLength={120} required /></label>
      <label>Record type<select name="mode"><option value="windows">Windows device</option><option value="visual">Other item · photos and condition</option>
        {session.data.simulator_enabled && <option value="simulator">Simulator · changed laptop</option>}</select></label>
      <Button type="submit" disabled={create.isPending}>Create handoff</Button>
    </form>
    <section className="panel form"><h2>Your handoffs</h2>
      {list.isPending ? <p role="status">Loading handoffs…</p> : list.items.length ? <ul className="records-list">{list.items.map(item => <li key={item.id}>
        <Link href={"/handoffs/" + item.id} className="quiet-link">{item.label}</Link><Status value={handoffLabels[item.status] ?? item.status} />
      </li>)}</ul> : <p>No handoffs yet.</p>}
      {list.hasNextPage && <LoadMore onClick={() => void list.fetchNextPage()}
        busy={list.isFetching} loading={list.isFetchingNextPage} />}
    </section></div>}
  </WorkspaceFrame>;
}

function DisplayComparison({ id, item }: { id: string; item: Handoff }) {
  const result = useQuery({ queryKey: ["handoff-report", id], queryFn: () => api<HandoffReport>("/handoffs/" + id + "/report") });
  const report = result.data?.payload;
  return <section className="panel form">
    <h2>Handoff comparison</h2>
    <ErrorNote error={result.error} />
    {result.isPending && <p role="status">Loading comparison…</p>}
    {report && <>
      <p className={result.data?.valid ? "notice good" : "notice warning"}>{result.data?.valid ? "Signature verified" : "Report signature is invalid"}</p>
      {report.mode === "simulator" && <p className="notice warning">SIMULATED DATA · For demonstration only.</p>}
      <p>Review recorded condition and matching-angle photos before deciding what changed.</p>
      <div className="table-scroll"><table><thead><tr><th scope="col">Check</th><th scope="col">Before</th><th scope="col">After</th><th scope="col">Result</th></tr></thead>
      <tbody>{report.differences.map(row => <tr key={row.metric}><th scope="row">{row.metric}</th>
        <td>{conditionLabels[String(row.before)] ?? row.before ?? "Unavailable"}</td><td>{conditionLabels[String(row.after)] ?? row.after ?? "Unavailable"}</td>
        <td><Status value={row.status === "MISMATCH" ? "Changed" : row.status === "MATCH" ? "Unchanged" : "Unavailable"} /></td>
      </tr>)}</tbody></table></div>
      {report.baseline.note && <p><strong>Baseline note</strong> {report.baseline.note}</p>}
      {report.return.note && <p><strong>Return note</strong> {report.return.note}</p>}
      {report.visual_findings?.length ? <><h3>Exterior comparison</h3>
        <div className="comparison-views">{report.visual_findings.map(view => <div key={view.angle}>
          <h4>{angleName[view.angle]}</h4><p>{view.detail}</p>
          <EvidenceGallery thumbnails items={item.photos.filter(phase => item.photo_views?.[phase]?.includes(view.angle)).map(phase => ({
            href: "/api/v1/handoffs/" + id + "/photos/" + phase + "?angle=" + view.angle,
            label: (phase === "baseline" ? "Baseline" : "Return") + " " + view.angle + " view",
          }))} />
        </div>)}</div></> : <EvidenceGallery items={item.photos.map(phase => ({
          href: "/api/v1/handoffs/" + id + "/photos/" + phase, label: "Open " + phase + " photo",
        }))} />}
      <p>Inspect the item in person. Matching photos cannot establish physical identity.</p>
      <Link href={"/verify/" + report.report_id} className="quiet-link">Check public signature</Link>
    </>}
  </section>;
}

export function HandoffDetail({ id }: { id: string }) {
  const path = "/handoffs/" + id;
  const key = ["handoff", id];
  const client = useQueryClient();
  const [ticket, setTicket] = useState<ScanTicket | null>(null);
  const [reading, setReading] = useState<File | null>(null);
  const [photo, setPhoto] = useState<File | null>(null);
  const [selected, setSelected] = useState<Angle | null>(null);
  const item = useQuery({ queryKey: key, queryFn: () => api<Handoff>(path) });
  function saved(updated: Handoff) {
    client.setQueryData(key, updated);
    void client.invalidateQueries({ queryKey: ["handoffs"] });
  }
  const start = useMutation({
    mutationFn: () => api<{ handoff: Handoff; ticket: ScanTicket | null }>(path + "/start", {}),
    onSuccess: data => {
      saved(data.handoff);
      setTicket(data.ticket);
      setReading(null);
      if (data.ticket) downloadTicket(data.ticket);
    },
  });
  const mark = useMutation({ mutationFn: (action: "activate" | "close") => api<Handoff>(path + "/" + action, {}), onSuccess: saved });
  const invite = useMutation({ mutationFn: () => api<{ url: string }>(path + "/invite", {}) });
  const upload = useMutation({
    mutationFn: async ({ file, angle }: { file: File; angle: Angle }) => {
      const response = await fetch("/api/v1" + path + "/photos?angle=" + angle, {
        method: "POST", headers: { "Content-Type": "image/jpeg" }, body: await jpeg(file),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Could not save this photo.");
      return data as Handoff;
    }, onSuccess: result => { saved(result); setPhoto(null); setSelected(null); },
  });
  const record = useMutation({
    mutationFn: async (data: FormData) => {
      let hardware: unknown;
      if (reading) {
        if (reading.size > 65_536) throw new Error("Choose a scan file under 64 KB.");
        try { hardware = JSON.parse(await reading.text()); }
        catch { throw new Error("Choose the JSON file exported by the Windows collector."); }
      }
      return api<Handoff>(path + "/record", { condition: data.get("condition") ?? "clean", note: data.get("note") ?? "", reading: hardware });
    },
    onSuccess: updated => { saved(updated); setReading(null); setPhoto(null); setTicket(null); setSelected(null); },
  });
  const data = item.data;
  const status = data?.status;
  const scanning = status === "BASELINE_SCANNING" || status === "RETURN_SCANNING";
  const phase = status === "RETURN_SCANNING" ? "return" : "baseline";
  const angle = selected ?? data?.next_view ?? "front";
  const baselineAngles = data?.photo_views?.baseline ?? [];
  const stage = status === "REPORT_READY" || status === "CLOSED" ? 3 : status === "RETURN_SCANNING" ? 2
    : status === "BASELINE_CREATED" || status === "ACTIVE_HANDOFF" ? 1 : 0;

  return <WorkspaceFrame page="Handoffs">
    <div className="page-title"><Link href="/handoffs" className="quiet-link">Your handoffs</Link><h1>{data?.label ?? "Handoff"}</h1>
      {status && <Status value={handoffLabels[status] ?? status} />}</div>
    {data && <ol className="steps" aria-label="Handoff progress">
      {["Baseline", "Handoff", "Return", "Compare"].map((label, index) =>
        <li key={label} className={index <= stage ? "reached" : ""} aria-current={index === stage ? "step" : undefined}><span>{index + 1}</span>{label}</li>)}
    </ol>}
    <ErrorNote error={item.error ?? start.error ?? record.error ?? mark.error ?? invite.error ?? upload.error} />
    {item.isPending && <p role="status">Opening handoff…</p>}
    {data?.mode === "simulator" && <p className="notice warning">SIMULATED DATA</p>}
    {(status === "DRAFT" || status === "ACTIVE_HANDOFF") && <section className="panel form">
      <h2>{status === "DRAFT" ? "Record the starting condition" : "Check the asset on return"}</h2>
      <Button disabled={start.isPending} onClick={() => start.mutate()}>{status === "DRAFT" ? "Start baseline" : "Start return check"}</Button>
    </section>}
    {data && scanning && <section className="panel form" key={phase}>
      <h2>{phase === "baseline" ? "Baseline checkpoint" : "Return checkpoint"}</h2>
      {data.mode === "windows" && <div className="actions">
        <Button variant="outline" onClick={() => start.mutate()} disabled={start.isPending}>{ticket ? "Download fresh ticket" : "Download scan ticket"}</Button>
        <a className={buttonVariants({ variant: "outline" })} href="/collect-windows.ps1" download>PowerShell collector</a>
      </div>}
      {data.mode !== "simulator" && <>
        <p>{data.next_view ? "Suggested next view: " + angleName[data.next_view] : "You can add another view or record this checkpoint."} {phase === "return" ? "Match the baseline angle, distance and lighting." : "Show the entire side. Keep faces and serial labels out of frame."}</p>
        {phase === "return" && (baselineAngles.includes(angle) || (!baselineAngles.length && data.photos.includes("baseline"))) && <EvidenceGallery items={[
          { href: "/api/v1" + path + "/photos/baseline" + (baselineAngles.length ? "?angle=" + angle : ""), label: "See baseline photo" },
        ]} />}
        <label>Checkpoint view<select value={angle} disabled={upload.isPending} onChange={event => {
          setSelected(event.target.value as Angle); setPhoto(null); upload.reset();
        }}>{views.map(view => <option key={view} value={view}>{angleName[view]}</option>)}</select></label>
        <CameraPicker key={phase + ":" + angle + ":" + (data.photo_views?.[phase]?.length ?? 0)}
          label="Checkpoint photo" onPhoto={setPhoto} disabled={upload.isPending} />
        <Button variant="outline" disabled={!photo || upload.isPending} onClick={() => { if (photo) upload.mutate({ file: photo, angle }); }}>
          {upload.isPending ? "Checking photo…" : "Check and save photo"}
        </Button>
        {data.capture_feedback && <p role="status"><strong>{angleName[data.capture_feedback.angle]}</strong> {data.capture_feedback.detail}</p>}
        {!!data.photo_views?.[phase]?.length && <p>Saved views: {data.photo_views[phase].map(view => angleName[view]).join(", ")}</p>}
      </>}
      <form className="form" onSubmit={event => { event.preventDefault(); record.mutate(new FormData(event.currentTarget)); }}>
        {data.mode === "windows" && <label>Windows scan file<input type="file" accept=".json,application/json" onChange={event => setReading(event.target.files?.[0] ?? null)} required /></label>}
        {data.mode !== "simulator" && <>
          <label>Exterior condition<select name="condition">{Object.entries(conditionLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
          <label>Notes<textarea name="note" rows={3} maxLength={400} /></label>
        </>}
        <Button type="submit" disabled={record.isPending || (data.mode === "visual" && !data.photos.includes(phase))}>
          {phase === "baseline" ? "Record baseline" : "Record return"}
        </Button>
      </form>
    </section>}
    {data && (status === "BASELINE_CREATED" || status === "ACTIVE_HANDOFF") && <section className="panel form">
      <h2>Receiver acceptance</h2>
      {data.receiver_accepted ? <p className="notice good">Receiver accepted.</p> : <>
        <p>Invite the receiver to acknowledge the handoff, or continue without their acceptance.</p>
        <Button variant="outline" disabled={invite.isPending} onClick={() => invite.mutate()}>Create acceptance link</Button>
        {invite.data && <label>Private acceptance link<input value={invite.data.url} readOnly onFocus={event => event.target.select()} /></label>}
        <Button variant="quiet" onClick={() => void item.refetch()}>Refresh acceptance</Button>
      </>}
      {status === "BASELINE_CREATED" && <Button onClick={() => mark.mutate("activate")} disabled={mark.isPending}>Mark as handed off</Button>}
    </section>}
    {data && (status === "REPORT_READY" || status === "CLOSED") && <>
      <DisplayComparison id={id} item={data} />
      {status === "REPORT_READY" && <Button variant="outline" onClick={() => mark.mutate("close")} disabled={mark.isPending}>Close handoff</Button>}
    </>}
  </WorkspaceFrame>;
}

export function AcceptHandoff({ id }: { id: string }) {
  const path = "/handoffs/" + id + "/accept";
  const key = ["handoff-acknowledgment", id] as const;
  const client = useQueryClient();
  const progress = useQuery({
    queryKey: key,
    queryFn: async () => {
      const result = await api<{ accepted: boolean }>(path);
      return { ...result, hasToken: /^[A-Za-z0-9_-]{43}$/.test(window.location.hash.slice(1)) };
    },
  });
  const accept = useMutation({
    mutationFn: () => api(path, { token: window.location.hash.slice(1) }),
    onSuccess: () => {
      window.history.replaceState(null, "", window.location.pathname);
      client.setQueryData(key, { accepted: true, hasToken: false });
    },
  });
  return <PublicShell isGuest><section className="panel form">
    <h1>Acknowledge a handoff</h1>
    <p>Accept to record when you acknowledged receiving the item.</p>
    <ErrorNote error={accept.error ?? progress.error} />
    {progress.isPending && <p role="status">Opening invitation…</p>}
    {progress.isError && <Button onClick={() => void progress.refetch()}>Try again</Button>}
    {progress.data?.accepted ? <p className="notice good" role="status">Acceptance recorded.</p>
      : progress.data?.hasToken ? <Button disabled={accept.isPending} onClick={() => accept.mutate()}>Accept handoff</Button>
        : progress.data && <p>Open the original private invitation to acknowledge this handoff.</p>}
  </section></PublicShell>;
}

"use client";

import { api, type Verification } from "@proofscan/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ErrorNote, PublicShell, Status } from "./shared";
import { Button } from "./ui/button";

type AuditEntry = { id: string; actor_id: string; target_id: string; action: string; reason: string; created_at: string };
type Metrics = { handoffs: Record<string, number>; scans: { platform: string; started: number; submitted: number }[];
  agent_runs: number; listing_mismatch_scans: number; evidence_bytes: number;
  model: { requests: number; accepted: number; input_tokens: number; output_tokens: number } };
type OperatorHandoff = { id: string; asset_id: string; label: string; status: string };

export function Operator() {
  const client = useQueryClient();
  const [identifier, setIdentifier] = useState("");
  const overview = useQuery({ queryKey: ["admin", "overview"], queryFn: () => api<Record<string, number>>("/admin/overview") });
  const audit = useQuery({ queryKey: ["admin", "audit"], enabled: overview.isSuccess, queryFn: () => api<AuditEntry[]>("/admin/audit") });
  const metrics = useQuery({ queryKey: ["admin", "metrics"], enabled: overview.isSuccess, queryFn: () => api<Metrics>("/admin/metrics") });
  const results = useQuery({ queryKey: ["admin", "search", identifier], enabled: !!identifier && overview.isSuccess,
    queryFn: async () => {
      const encoded = encodeURIComponent(identifier);
      const [verifications, handoffs] = await Promise.all([
        api<Verification[]>("/admin/search/" + encoded), api<OperatorHandoff[]>("/admin/handoffs/search/" + encoded),
      ]);
      return { verifications, handoffs };
    } });
  const action = useMutation({
    mutationFn: ({ path, reason }: { path: string; reason: string }) => api(path, { reason }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["admin"] }),
  });
  return <PublicShell>
    <div className="page-title"><h1>ProofScan operator</h1><p>Review verification activity and manage report validity.</p></div>
    <ErrorNote error={overview.error ?? audit.error ?? metrics.error ?? results.error ?? action.error} />
    {overview.isPending && <p role="status">Checking operator access…</p>}
    {overview.data && <>
      <section className="panel form"><h2>Verification status</h2>
        <div className="actions">{Object.entries(overview.data).map(([state, count]) => <span key={state}><Status value={state} /> {count}</span>)}</div>
        {!Object.keys(overview.data).length && <p>No verifications have been created.</p>}
      </section>
      {metrics.data && <section className="panel form">
        <h2>Operations</h2><dl className="technical">
          <dt>Handoffs</dt><dd>{Object.values(metrics.data.handoffs).reduce((sum, value) => sum + value, 0)}</dd>
          <dt>Inspection runs</dt><dd>{metrics.data.agent_runs}</dd>
          <dt>Real scans with claim discrepancies</dt><dd>{metrics.data.listing_mismatch_scans}</dd>
          <dt>Stored photos</dt><dd>{Math.round(metrics.data.evidence_bytes / 1024).toLocaleString()} KiB</dd>
          <dt>Model requests</dt><dd>{metrics.data.model.accepted} successful of {metrics.data.model.requests}</dd>
          <dt>Model tokens</dt><dd>{metrics.data.model.input_tokens} input, {metrics.data.model.output_tokens} output</dd>
        </dl>
        {!!metrics.data.scans.length && <div className="table-scroll"><table>
          <caption>Scans by platform</caption><thead><tr><th>Platform</th><th>Started</th><th>Submitted</th></tr></thead>
          <tbody>{metrics.data.scans.map(row => <tr key={row.platform}><th scope="row">{row.platform}</th><td>{row.started}</td><td>{row.submitted}</td></tr>)}</tbody>
        </table></div>}
      </section>}
      <form className="panel form" onSubmit={event => {
        event.preventDefault();
        const value = String(new FormData(event.currentTarget).get("search") ?? "").trim();
        if (value === identifier) void results.refetch();
        else setIdentifier(value);
      }}>
        <h2>Find an activity record</h2><label>Verification, handoff, asset, report or user ID<input name="search" required /></label>
        <Button type="submit">Search</Button>
        {results.data && (results.data.verifications.length + results.data.handoffs.length
          ? <ul className="records-list">{[...results.data.verifications, ...results.data.handoffs].map(item => <li key={item.id}><strong>{item.label}</strong><Status value={item.status} /><code>{item.id}</code></li>)}</ul>
          : <p>No results.</p>)}
      </form>
      <form className="panel form" onSubmit={event => {
        event.preventDefault();
        const data = new FormData(event.currentTarget);
        const id = encodeURIComponent(String(data.get("target")).trim());
        const path = data.get("action") === "revoke" ? "/admin/verifications/" + id + "/revoke" : "/admin/reports/" + id + "/invalidate";
        action.mutate({ path, reason: String(data.get("reason")) });
      }}>
        <h2>Take an action</h2>
        <label>Action<select name="action"><option value="revoke">Revoke a seller link</option><option value="invalidate">Invalidate a signed report</option></select></label>
        <label>Verification or report ID<input name="target" required /></label>
        <label>Reason<input name="reason" required minLength={8} maxLength={280} /></label>
        {action.isSuccess && <p className="notice good" role="status">Action recorded.</p>}
        <Button type="submit" disabled={action.isPending}>Apply action</Button>
      </form>
      <section className="panel form"><h2>Recent audit entries</h2>
        {audit.data?.length
          ? <ul className="records-list">{audit.data.map(item => <li key={item.id}><div><strong>{item.action === "revoke_guest" ? "Seller link revoked" : "Report invalidated"}</strong><p>{item.reason}</p><code>{item.target_id}</code></div><time dateTime={item.created_at}>{new Date(item.created_at).toLocaleString()}</time></li>)}</ul>
          : <p>No audit entries.</p>}
      </section>
    </>}
  </PublicShell>;
}

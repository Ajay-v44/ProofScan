"use client";

import { api, type Claims, type Verification } from "@proofscan/api-client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, Copy } from "lucide-react";
import { useState, type FormEvent } from "react";
import { ErrorNote } from "./shared";
import { Button, buttonVariants } from "./ui/button";

type Created = Verification & { guest_url: string };

function optionalNumber(form: FormData, name: string) {
  const value = form.get(name);
  return value ? Number(value) : undefined;
}

export function NewVerification({ onClose, onComplete, listingAssistance }: { onClose: () => void; onComplete: () => void; listingAssistance: boolean }) {
  const client = useQueryClient();
  const [copied, setCopied] = useState(false);
  const [copyFailed, setCopyFailed] = useState(false);
  const [listing, setListing] = useState("");
  const [specs, setSpecs] = useState({ memory: "", storage: "", battery: "" });
  const suggest = useMutation({
    mutationFn: () => api<Claims>("/claims/suggest", { listing }),
    onSuccess: claims => setSpecs(previous => ({
      memory: claims.memory_gib != null ? String(claims.memory_gib) : previous.memory,
      storage: claims.storage_gb != null ? String(claims.storage_gb) : previous.storage,
      battery: claims.battery_percent != null ? String(claims.battery_percent) : previous.battery,
    })),
  });
  const create = useMutation({
    mutationFn: (data: { label: FormDataEntryValue | null; claims: Claims }) => api<Created>("/verifications", data),
    onSuccess: () => client.invalidateQueries({ queryKey: ["verifications"] }),
  });
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    create.mutate({ label: form.get("label"), claims: {
      memory_gib: optionalNumber(form, "memory"), storage_gb: optionalNumber(form, "storage"),
      battery_percent: optionalNumber(form, "battery"),
    } });
  }
  if (create.data) return <div className="dialog-form">
    <div className="verification-success" role="status">
      <div className="icon-tile mint"><Check size={22} aria-hidden /></div>
      <div><h2>Your seller link is ready</h2><p>Send this link directly to the seller. It expires in 48 hours.</p></div>
    </div>
    <label>Private seller link<input readOnly value={create.data.guest_url} onFocus={event => event.currentTarget.select()} /></label>
    <div className="actions">
      <Button onClick={async () => {
        try { await navigator.clipboard.writeText(create.data.guest_url); setCopied(true); setCopyFailed(false); }
        catch { setCopyFailed(true); }
      }}><Copy size={17} aria-hidden />{copied ? "Copied" : "Copy link"}</Button>
      <a className={buttonVariants({ variant: "outline" })} href={create.data.guest_url} rel="noreferrer">Open seller link</a>
      <Button variant="quiet" onClick={onComplete}>Done</Button>
    </div>
    {copyFailed && <p className="notice" role="status">Select the link above and copy it manually.</p>}
  </div>;
  return <form className="dialog-form" onSubmit={submit}>
    <label>Device name<input data-dialog-autofocus name="label" placeholder="e.g. ThinkPad T14 Gen 3" maxLength={120} required /></label>
    <fieldset className="verification-fields"><legend>Seller’s advertised specs</legend>
    <p>Leave fields blank if the listing doesn’t include them. These values will be compared with the seller’s scan.</p>
    {listingAssistance && <details><summary>Suggest claims from listing text</summary>
      <div className="form"><label>Listing text<textarea value={listing} onChange={event => setListing(event.target.value)} maxLength={2400} rows={4} /></label>
        <p>ProofScan sends this text to Moonshot when you request suggestions. Remove contact details first and check the suggested specs.</p>
        <Button variant="outline" disabled={listing.trim().length < 8 || suggest.isPending} onClick={() => suggest.mutate()}>Suggest claims</Button>
        <ErrorNote error={suggest.error} />
      </div></details>}
    <div className="input-grid">
      <label>Memory (GiB)<input name="memory" type="number" min={1} max={1024} placeholder="16" value={specs.memory} onChange={event => setSpecs({ ...specs, memory: event.target.value })} /></label>
      <label>Largest drive (GB)<input name="storage" type="number" min={1} max={10000000} placeholder="1000" value={specs.storage} onChange={event => setSpecs({ ...specs, storage: event.target.value })} /></label>
      <label>Minimum battery health (%)<input name="battery" type="number" min={0} max={100} placeholder="85" value={specs.battery} onChange={event => setSpecs({ ...specs, battery: event.target.value })} /></label>
    </div>
    </fieldset>
    <ErrorNote error={create.error} />
    <div className="actions"><Button type="submit" disabled={create.isPending}>Create seller link</Button><Button variant="quiet" onClick={onClose}>Cancel</Button></div>
  </form>;
}



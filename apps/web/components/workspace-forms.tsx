"use client";

import { api, type Claims, type Verification } from "@proofscan/api-client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, Copy } from "lucide-react";
import { useState, type FormEvent } from "react";
import { ErrorNote } from "./shared";
import { Button, buttonVariants } from "./ui/button";
import { Dialog } from "./ui/dialog";

type Created = Verification & { guest_url: string };

function optionalNumber(form: FormData, name: string) {
  const value = form.get(name);
  return value ? Number(value) : undefined;
}

export function AuthDialog({ initialRegister, onAuthenticated, onClose }: {
  initialRegister: boolean; onAuthenticated: () => void; onClose: () => void;
}) {
  const client = useQueryClient();
  const [register, setRegister] = useState(initialRegister);
  const auth = useMutation({
    mutationFn: (data: { email: FormDataEntryValue | null; password: FormDataEntryValue | null }) =>
      api<{ message?: string }>(register ? "/auth/register" : "/auth/login", data),
    onSuccess: async result => {
      if (!result.message) {
        await client.invalidateQueries({ queryKey: ["session"] });
        onAuthenticated();
      }
    },
  });
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    auth.mutate({ email: form.get("email"), password: form.get("password") });
  }
  return <Dialog title={register ? "Create an account" : "Sign in"} onClose={onClose}>
    <form className="dialog-form" onSubmit={submit}>
    <label>Email<input data-dialog-autofocus type="email" name="email" autoComplete="email" required /></label>
    <label>Password<input type="password" name="password" autoComplete={register ? "new-password" : "current-password"} required minLength={12} maxLength={128} /></label>
    <ErrorNote error={auth.error} />
    {auth.data?.message && <p className="notice" role="status">{auth.data.message}</p>}
    <div className="actions">
      <Button type="submit" disabled={auth.isPending}>{register ? "Create account" : "Sign in"}</Button>
      <Button variant="quiet" onClick={() => { auth.reset(); setRegister(!register); }}>{register ? "Back to sign in" : "Create an account"}</Button>
    </div>
    </form>
  </Dialog>;
}

export function NewVerification({ onClose, listingAssistance }: { onClose: () => void; listingAssistance: boolean }) {
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
    <div className="icon-tile mint"><Check size={22} aria-hidden /></div>
    <div><h2>Your seller link is ready</h2><p>Copy it now and send it to the seller. It expires in 48 hours.</p></div>
    <label>Private seller link<input readOnly value={create.data.guest_url} onFocus={event => event.currentTarget.select()} /></label>
    <div className="actions">
      <Button onClick={async () => {
        try { await navigator.clipboard.writeText(create.data.guest_url); setCopied(true); setCopyFailed(false); }
        catch { setCopyFailed(true); }
      }}><Copy size={17} aria-hidden />{copied ? "Copied" : "Copy link"}</Button>
      <a className={buttonVariants({ variant: "outline" })} href={create.data.guest_url} rel="noreferrer">Open seller link</a>
      <Button variant="quiet" onClick={onClose}>Done</Button>
    </div>
    {copyFailed && <p className="notice" role="status">Select the link above and copy it manually.</p>}
  </div>;
  return <form className="dialog-form" onSubmit={submit}>
    <p>Name the device and optionally add the specs the seller advertised.</p>
    <label>Device name<input data-dialog-autofocus name="label" placeholder="e.g. ThinkPad T14 Gen 3" maxLength={120} required /></label>
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
    <ErrorNote error={create.error} />
    <div className="actions"><Button type="submit" disabled={create.isPending}>Create seller link</Button><Button variant="quiet" onClick={onClose}>Cancel</Button></div>
  </form>;
}



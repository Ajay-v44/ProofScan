"use client";

import { api, ApiError } from "@proofscan/api-client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState, type FormEvent } from "react";
import { accountHref } from "./account-navigation";
import { ErrorNote, PublicShell } from "./shared";
import { Button, buttonVariants } from "./ui/button";

type Deletion = { provider_pending: boolean };

export function DeleteAccount() {
  const client = useQueryClient();
  const [completed, setCompleted] = useState<Deletion>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const session = useQuery({
    queryKey: ["session"], enabled: !completed,
    queryFn: () => api<{ user_id: string }>("/auth/session"),
  });
  const signedOut = session.error instanceof ApiError && session.error.status === 401;
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const form = event.currentTarget;
    const password = new FormData(form).get("password");
    form.reset();
    setBusy(true);
    setError(null);
    try {
      setCompleted(await api<Deletion>("/auth/delete-account", { password }));
      client.clear();
    } catch (failure) {
      setError(failure);
    } finally {
      setBusy(false);
    }
  }

  return <PublicShell><section className="panel form">
    <h1>Delete your ProofScan account</h1>
    {completed ? <>
      <p role="status">{completed.provider_pending
        ? "Your workspace data was deleted. Your sign-in account is scheduled for deletion."
        : "Your account and workspace data were deleted."}</p>
      <Link href="/">Return to ProofScan</Link>
    </> : <>
      <p>Deleting your account permanently removes your verifications, handoffs, signed reports, and photos. Private links will stop working.</p>
      <Link href="/privacy">Read the privacy and retention policy</Link>
      {session.isPending && <p role="status">Checking your session…</p>}
      {signedOut && <Link className={buttonVariants()} href={accountHref("sign-in", "/account/delete")}>Sign in to continue</Link>}
      <ErrorNote error={signedOut ? null : session.error} />
      {session.isError && !signedOut && <Button onClick={() => void session.refetch()}>Try again</Button>}
      {session.data && !session.isError && <form className="form" onSubmit={submit}>
        <label>Current password<input type="password" name="password" autoComplete="current-password"
          minLength={12} maxLength={128} disabled={busy} required /></label>
        <label className="checkbox"><input type="checkbox" name="confirmation" required />I understand that deletion is permanent.</label>
        <ErrorNote error={error} />
        <div className="actions">
          <Button type="submit" disabled={busy}>{busy ? "Deleting account…" : "Permanently delete account"}</Button>
          <Link href="/profile">Cancel</Link>
        </div>
      </form>}
    </>}
  </section></PublicShell>;
}

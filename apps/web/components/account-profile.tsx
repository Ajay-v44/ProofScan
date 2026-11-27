"use client";

import { api, ApiError } from "@proofscan/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, CalendarDays, KeyRound, LogOut, ShieldCheck, UserRound } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { accountHref } from "./account-navigation";
import { ErrorNote } from "./shared";
import { Button, buttonVariants } from "./ui/button";
import { WorkspaceFrame } from "./workspace-frame";
import "./account.css";

type Profile = {
  email: string | null;
  display_name: string | null;
  created_at: string;
  recovery_method: "email" | "code";
  recovery_code_ready: boolean;
};

export function AccountProfile() {
  const session = useQuery({ queryKey: ["session"], queryFn: () => api<{ user_id: string }>("/auth/session") });
  const signedOut = session.error instanceof ApiError && session.error.status === 401;
  return <WorkspaceFrame page="Profile">
    {session.isPending && <p role="status">Opening profile…</p>}
    <ErrorNote error={signedOut ? null : session.error} />
    {signedOut && <section className="panel form"><h1>Your profile</h1><p>Sign in to edit your profile and recovery settings.</p>
      <Link className={buttonVariants()} href={accountHref("sign-in", "/profile")}>Sign in</Link></section>}
    {session.data && !session.isError && <ProfileDetails key={session.data.user_id} owner={session.data.user_id} />}
  </WorkspaceFrame>;
}

function ProfileDetails({ owner }: { owner: string }) {
  const router = useRouter();
  const client = useQueryClient();
  const key = ["account-profile", owner];
  const profile = useQuery({ queryKey: key, queryFn: () => api<Profile>("/auth/profile") });
  const [code, setCode] = useState<string>();
  const [codeStatus, setCodeStatus] = useState("");
  const [generating, setGenerating] = useState(false);
  const [codeError, setCodeError] = useState<unknown>(null);
  const save = useMutation({ mutationFn: (name: string) => api<Profile>("/auth/profile", { display_name: name }),
    onSuccess: result => { client.setQueryData(key, result); } });
  const signOut = useMutation({ mutationFn: () => api("/auth/logout", {}), onSuccess: () => {
    client.clear(); router.replace("/sign-in");
  } });

  async function generate() {
    setGenerating(true);
    setCodeError(null);
    setCodeStatus("");
    try {
      const result = await api<{ code: string }>("/auth/recovery-code", {});
      setCode(result.code);
      await client.invalidateQueries({ queryKey: key });
    } catch (error) {
      setCodeError(error);
    } finally {
      setGenerating(false);
    }
  }

  async function copyCode() {
    if (!code) return;
    try { await navigator.clipboard.writeText(code); setCodeStatus("Recovery code copied."); }
    catch { setCodeStatus("Select and copy the code manually."); }
  }

  if (profile.isPending) return <p role="status">Loading profile…</p>;
  if (!profile.data) return <ErrorNote error={profile.error} />;
  const account = profile.data;
  const name = account.display_name || account.email?.split("@")[0] || "ProofScan member";
  const memberSince = new Intl.DateTimeFormat(undefined, { month: "long", year: "numeric" }).format(new Date(account.created_at));

  function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    save.mutate(String(new FormData(event.currentTarget).get("display_name") ?? ""));
  }

  return <>
    <section className="profile-cover">
      <span aria-hidden className="profile-avatar">{name.split(/\s+/).slice(0, 2).map(part => Array.from(part)[0]?.toUpperCase()).join("")}</span>
      <div className="profile-identity"><h1>Your profile</h1><p>{name}</p>
        <span><CalendarDays size={16} aria-hidden /> Member since {memberSince}</span></div>
    </section>
    <div className="profile-grid">
      <section className="panel profile-panel" aria-labelledby="personal-title">
        <header><UserRound size={21} aria-hidden /><h2 id="personal-title">Personal details</h2></header>
        <form className="form" onSubmit={saveProfile} onChange={() => { if (save.isSuccess || save.isError) save.reset(); }}>
          <label>Display name<input name="display_name" defaultValue={account.display_name ?? ""} maxLength={60} autoComplete="nickname" /></label>
          {account.email && <label>Sign-in email<input value={account.email} readOnly /></label>}
          <ErrorNote error={save.error} />
          {save.isSuccess && <p className="notice good" role="status">Profile saved.</p>}
          <Button type="submit" disabled={save.isPending}>{save.isPending ? "Saving…" : "Save changes"}</Button>
        </form>
      </section>
      <section className="panel profile-panel" aria-labelledby="security-title">
        <header><KeyRound size={21} aria-hidden /><h2 id="security-title">Password and recovery</h2></header>
        {account.recovery_method === "code" ? <>
          <p>Save a recovery code somewhere private so you can reset your password if you lose access.</p>
          {account.recovery_code_ready && !code && <p className="field-hint">A recovery code is set. Replacing it invalidates the previous one.</p>}
          {code ? <div className="form">
            <label>New recovery code<input readOnly value={code} onFocus={event => event.currentTarget.select()} /></label>
            <p className="notice warning">Save this code now. It’s shown once and can be used once.</p>
            <div className="actions"><Button variant="outline" onClick={() => void copyCode()}>Copy code</Button>
              <Button variant="quiet" onClick={() => { setCode(undefined); setCodeStatus(""); }}>Done</Button></div>
            {codeStatus && <p role="status">{codeStatus}</p>}
          </div> : <Button variant="outline" disabled={generating} onClick={() => void generate()}>
            {generating ? "Generating…" : account.recovery_code_ready ? "Replace recovery code" : "Generate recovery code"}
          </Button>}
          <ErrorNote error={codeError} />
          <Link href="/reset-password" className="quiet-link">Use a recovery code</Link>
        </> : <><p>Request a one-time code at your sign-in email to choose a new password.</p>
          <Link href="/forgot-password" className={buttonVariants({ variant: "outline" })}>Reset password</Link></>}
      </section>
      <section className="panel profile-panel profile-session">
        <header><ShieldCheck size={21} aria-hidden /><h2>Account and privacy</h2></header>
        <Link href="/privacy" className="quiet-link">Privacy and evidence retention <ArrowRight size={16} aria-hidden /></Link>
        <Link href="/account/delete" className="quiet-link">Delete account <ArrowRight size={16} aria-hidden /></Link>
        <ErrorNote error={signOut.error} />
        <Button variant="outline" disabled={signOut.isPending} onClick={() => signOut.mutate()}><LogOut size={17} aria-hidden />Sign out</Button>
      </section>
    </div>
  </>;
}

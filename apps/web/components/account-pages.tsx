"use client";

import { api } from "@proofscan/api-client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, Check, Eye, EyeOff, KeyRound, Mail } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useId, useState, type FormEvent } from "react";
import { accountHref } from "./account-navigation";
import { Brand, ErrorNote } from "./shared";
import { Button, buttonVariants } from "./ui/button";
import "./account.css";

type Mode = "sign-in" | "sign-up" | "forgot-password" | "reset-password";
type RecoveryMethod = "email" | "code";
const content = {
  "sign-in": { title: "Sign in", intro: "Open your verification reports and handoffs.", action: "Sign in" },
  "sign-up": { title: "Create an account", intro: "Start a device check or record the condition of an item you’re handing over.", action: "Create account" },
  "forgot-password": { title: "Forgot your password?", intro: "Choose how to recover access to your ProofScan account.", action: "Send recovery code" },
  "reset-password": { title: "Set a new password", intro: "Enter your recovery code and choose a new password.", action: "Save new password" },
} satisfies Record<Mode, { title: string; intro: string; action: string }>;

function PasswordInput({ mode }: { mode: Mode }) {
  const [show, setShow] = useState(false);
  const id = useId();
  const fresh = mode !== "sign-in";
  return <div className="account-field">
    <div className="account-label-row">
      <label htmlFor={id}>{mode === "reset-password" ? "New password" : "Password"}</label>
      {!fresh && <Link href="/forgot-password">Forgot password?</Link>}
    </div>
    <div className="password-input">
      <input id={id} type={show ? "text" : "password"} name="password" minLength={12} maxLength={128}
        autoComplete={fresh ? "new-password" : "current-password"} aria-describedby={fresh ? `${id}-hint` : undefined} required />
      <button className="icon-button" type="button" aria-controls={id} aria-label={show ? "Hide password" : "Show password"}
        onClick={() => setShow(value => !value)}>{show ? <EyeOff size={19} aria-hidden /> : <Eye size={19} aria-hidden />}</button>
    </div>
    {fresh && <p id={`${id}-hint`} className="field-hint">Use at least 12 characters.</p>}
  </div>;
}

export function AccountPage({ mode, next = "/workspace" }: { mode: Mode; next?: string }) {
  const { title, intro, action } = content[mode];
  const router = useRouter();
  const queryClient = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [done, setDone] = useState<string>();
  const recovery = mode === "forgot-password" || mode === "reset-password";
  const options = useQuery({
    queryKey: ["recovery-options"], enabled: recovery,
    queryFn: () => api<{ method: RecoveryMethod }>("/auth/recovery"),
  });
  const local = options.data?.method === "code";
  const resetUrl = "/reset-password";

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    setError(null);
    setBusy(true);
    try {
      const email = data.get("email");
      if (mode === "forgot-password") {
        await api("/auth/recover", { email });
        setDone("If this address has an account, look for a recovery code in your email.");
      } else if (mode === "reset-password") {
        await api("/auth/reset", { email, code: data.get("code"), password: data.get("password") });
        form.reset();
        queryClient.clear();
        setDone("Your password has been updated. Sign in with your new password.");
      } else {
        const result = await api<{ message?: string }>(mode === "sign-up" ? "/auth/register" : "/auth/login", { email, password: data.get("password") });
        form.reset();
        if (result.message) setDone(result.message);
        else {
          queryClient.clear();
          router.replace(next);
        }
      }
    } catch (failure) {
      setError(failure);
    } finally {
      setBusy(false);
    }
  }

  return <div className="account-page">
    <a className="skip-link" href="#main">Skip to content</a>
    <header className="account-header"><Brand /><Link href="/workspace" className="account-back"><ArrowLeft size={16} aria-hidden />Workspace</Link></header>
    <main id="main" tabIndex={-1} className="account-layout">
      <aside className="account-visual" aria-label="About ProofScan">
        <Image src="/brand/account-inspection.webp" alt="" fill unoptimized preload />
        <div className="account-visual-copy"><h2>Used tech.<br />Real evidence.</h2>
          <p>Check the readings and photos before you buy. Compare what changed at pickup.</p>
          <Link href="/home#demo">Explore a sample report <ArrowRight size={16} aria-hidden /></Link>
        </div>
      </aside>
      <section className="account-panel" aria-labelledby="account-title">
        <div className="account-panel-inner">
          <header className="account-copy">
            {recovery && <span className="account-symbol"><KeyRound size={22} aria-hidden /></span>}
            <h1 id="account-title">{title}</h1><p>{intro}</p>
          </header>
          {recovery && options.isPending && <p role="status">Checking recovery options…</p>}
          {recovery && options.isError && <><ErrorNote error={options.error} /><Button variant="outline" onClick={() => void options.refetch()}>Try again</Button></>}
          {done ? <div className="account-complete" role="status">
            {mode === "forgot-password" ? <Mail size={22} aria-hidden /> : <Check size={22} aria-hidden />}
            <p>{done}</p><Link className={buttonVariants()} href={mode === "forgot-password" ? resetUrl : accountHref("sign-in", next)}>
              {mode === "forgot-password" ? "Enter recovery code" : "Go to sign in"}<ArrowRight size={17} aria-hidden />
            </Link>
          </div> : mode === "forgot-password" && local ? <div className="account-form">
            <p>Use the recovery code you saved from your profile. If you still have an active session, you can generate a new code there.</p>
            <Link className={buttonVariants()} href={resetUrl}>Use a recovery code <ArrowRight size={17} aria-hidden /></Link>
          </div> : (!recovery || options.data) && <form className="account-form" onSubmit={submit}>
            <label className="account-field">Email address<input type="email" name="email" autoComplete="username" maxLength={254} required /></label>
            {mode === "reset-password" && <label className="account-field">Recovery code<input name="code" autoComplete="one-time-code" autoCapitalize="none" spellCheck={false}
              inputMode={local ? "text" : "numeric"} maxLength={43} minLength={6} required /></label>}
            {mode !== "forgot-password" && <PasswordInput mode={mode} />}
            <ErrorNote error={error} />
            <Button className="account-submit" type="submit" disabled={busy}>
              {busy ? "Please wait…" : action}<ArrowRight size={17} aria-hidden />
            </Button>
          </form>}
          <p className="account-switch">
            {mode === "sign-in" ? <>New to ProofScan? <Link href={accountHref("sign-up", next)}>Create an account</Link></>
              : mode === "sign-up" ? <>Already have an account? <Link href={accountHref("sign-in", next)}>Sign in</Link></>
                : <Link href={accountHref("sign-in", next)}>Back to sign in</Link>}
          </p>
        </div>
        <footer className="account-footer"><Link href="/help">Help</Link><Link href="/privacy">Privacy</Link></footer>
      </section>
    </main>
  </div>;
}

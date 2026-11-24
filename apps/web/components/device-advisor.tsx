"use client";

import { api, apiDelete, ApiError, type AdvisorResult, type CatalogItem } from "@proofscan/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRef, useState, type FormEvent } from "react";
import { LoadMore } from "./owner-collection";
import { ErrorNote } from "./shared";
import { WorkspaceFrame } from "./workspace-frame";
import { Button } from "./ui/button";
import { AuthDialog } from "./workspace-forms";

const pageSize = 30;
const categories = [["phone", "Phone"], ["tablet", "Tablet"], ["laptop", "Laptop"], ["other", "Other"]];
const starterQuestions = ["Which has the healthiest battery?", "Which has the most memory?", "Compare storage capacity"];
const measurements = [
  ["battery_health_percent", "Battery health", "%"],
  ["memory_gib", "Memory", " GiB"],
  ["storage_gb", "Storage", " GB"],
] as const;

function CategoryInput({ label, all = false }: { label: string; all?: boolean }) {
  return <label>{label}<select name="category" defaultValue={all ? "" : "phone"}>
    {all && <option value="">All devices</option>}
    {categories.map(([value, text]) => <option key={value} value={value}>{text}</option>)}
  </select></label>;
}

function PriceFields({ label }: { label: string }) {
  return <div className="advisor-price">
    <label>{label}<input type="number" name="amount" min={1} max={100_000_000} /></label>
    <label>Currency<input name="currency" placeholder="INR" pattern="[A-Z]{3}" maxLength={3} /></label>
  </div>;
}

function priceFields(data: FormData) {
  const value = String(data.get("amount") ?? "").trim();
  return { amount: value ? Number(value) : null, currency: String(data.get("currency") ?? "").trim() || null };
}

function Source({ item }: { item: CatalogItem }) {
  return <>
    <strong>{item.title}</strong>
    {item.price !== null && <span>{item.facts?.estimated_price ? "Comparable estimate up to " : ""}{item.currency} {item.price.toLocaleString()}</span>}
    {item.verification_id ? <dl className="advisor-measurements">{measurements.map(([field, label, unit]) => {
      const value = item.facts?.[field];
      return <div key={field}><dt>{label}</dt><dd>{typeof value === "number" ? value.toLocaleString() + unit : "Unavailable"}</dd></div>;
    })}</dl> : <p>{item.notes}</p>}
    {item.verification_id && <Link className="quiet-link" href={"/reports/" + item.verification_id}>Open signed report</Link>}
    {item.source_url && <a className="quiet-link" href={item.source_url} rel="noreferrer">Open source</a>}
  </>;
}

export function DeviceAdvisor() {
  const [signIn, setSignIn] = useState(false);
  const session = useQuery({ queryKey: ["session"], queryFn: () => api<{ user_id: string }>("/auth/session") });
  const loggedOut = session.error instanceof ApiError && session.error.status === 401;

  return <WorkspaceFrame page="Buyer chat">
    <div className="page-title"><h1>Buyer chat</h1>
      <p>Ask which device is the better buy using signed reports shared with you.</p></div>
    <ErrorNote error={loggedOut ? null : session.error} />
    {session.isPending && <p role="status">Opening your catalog…</p>}
    {loggedOut && <section className="panel form">
      <p>Sign in to use your private catalog.</p>
      <Button onClick={() => setSignIn(true)}>Sign in</Button>
    </section>}
    {signIn && !session.data && <AuthDialog initialRegister={false} onAuthenticated={() => setSignIn(false)} onClose={() => setSignIn(false)} />}
    {session.data && !session.isError && <AdvisorForms key={session.data.user_id} owner={session.data.user_id} />}
  </WorkspaceFrame>;
}

function AdvisorForms({ owner }: { owner: string }) {
  const client = useQueryClient();
  const composer = useRef<HTMLTextAreaElement>(null);
  const [offset, setOffset] = useState(0);
  const [turns, setTurns] = useState<{ question: string; answer: AdvisorResult }[]>([]);
  const listKey = ["advisor-catalog", owner] as const;
  const catalog = useQuery({
    queryKey: [...listKey, offset],
    queryFn: () => api<CatalogItem[]>("/agent/catalog?offset=" + offset),
  });
  const ask = useMutation({
    mutationFn: (data: FormData) => {
      const { amount, currency } = priceFields(data);
      const question = String(data.get("question") ?? "").trim();
      return api<AdvisorResult>("/agent/ask", {
        question,
        previous_question: turns.at(-1)?.question,
        category: String(data.get("category") ?? "") || null,
        reports_only: data.get("include_listings") !== "on",
        budget: amount, currency, allow_model: data.get("allow_model") === "on",
      }).then(answer => ({ question, answer }));
    },
    onSuccess: turn => setTurns(current => [...current.slice(-9), turn]),
  });
  const add = useMutation({
    mutationFn: (data: FormData) => {
      const { amount, currency } = priceFields(data);
      return api<CatalogItem>("/agent/catalog", {
        title: String(data.get("title")), category: String(data.get("category")), notes: String(data.get("notes")),
        price: amount, currency, source_url: String(data.get("source_url") ?? "").trim() || null,
      });
    },
    onSuccess: () => {
      setOffset(0);
      return client.invalidateQueries({ queryKey: listKey });
    },
  });
  const remove = useMutation({
    mutationFn: (id: string) => apiDelete("/agent/catalog/" + id),
    onSuccess: () => {
      setOffset(current => catalog.data?.length === 1 ? Math.max(0, current - pageSize) : current);
      return client.invalidateQueries({ queryKey: listKey });
    },
  });

  function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    add.mutate(new FormData(form), { onSuccess: () => form.reset() });
  }

  return <div className="advisor-layout">
    <section className="panel form advisor-panel">
      <div className="advisor-heading"><h2>Compare devices</h2>
        {turns.length > 0 && <Button variant="quiet" onClick={() => { setTurns([]); ask.reset(); composer.current?.focus(); }} disabled={ask.isPending}>Clear chat</Button>}
      </div>
      {!turns.length && <div className="advisor-starters" aria-label="Suggested questions" role="group">
        {starterQuestions.map(question => <Button key={question} variant="outline" onClick={() => {
          if (!composer.current) return;
          composer.current.value = question;
          composer.current.focus();
        }}>{question}</Button>)}
      </div>}
      <div className="advisor-chat" role="log" aria-live="polite" aria-label="Conversation">
        {turns.map(({ question, answer }, index) => <section className="advisor-turn" key={index}>
          <p><strong>You</strong> {question}</p>
          <h3>{answer.status === "answer" ? "Recommendation" : answer.status === "needs_input" ? "One more detail" : "No matching evidence"}</h3>
          <p>{answer.message}</p>
          {answer.sources.length > 0 && <><h4>Sources from your catalog</h4>
            <ul className="advisor-source-cards">{answer.sources.map(item => <li key={item.id}><Source item={item} /></li>)}</ul></>}
        </section>)}
      </div>
      <form className="form" onSubmit={event => {
        event.preventDefault();
        const form = event.currentTarget;
        ask.mutate(new FormData(form), { onSuccess: () => {
          if (composer.current) { composer.current.value = ""; composer.current.focus(); }
        } });
      }}>
        <label>What are you looking for?<textarea ref={composer} name="question" rows={3} minLength={3} maxLength={600}
          placeholder="Ask about the devices you’re considering" readOnly={ask.isPending} required /></label>
        <details className="advisor-options" onInvalid={event => { event.currentTarget.open = true; }}><summary>Filters and AI options</summary>
          <div className="form"><CategoryInput label="Device type" all />
            <PriceFields label="Maximum budget" />
            <label className="checkbox"><input type="checkbox" name="include_listings" />Include my saved listings</label>
            <label className="checkbox"><input type="checkbox" name="allow_model" />Use Moonshot for this comparison</label>
            <p className="muted">Only structured measurements, prices and recognized preferences are sent to Moonshot.</p>
          </div>
        </details>
        <Button type="submit" disabled={ask.isPending}>Get a recommendation</Button>
        {ask.isPending && <p role="status" className="muted">Checking your evidence…</p>}
      </form>
      <ErrorNote error={ask.error} />
    </section>
    <section className="panel form advisor-library">
      <h2>Saved listings</h2>
      <p className="muted">Keep listings you’re considering. Add them to a comparison with the chat filters.</p>
      <details onInvalid={event => { event.currentTarget.open = true; }}><summary>Add a listing</summary>
      <form className="form" onSubmit={save}>
        <label>Device name<input name="title" minLength={2} maxLength={120} required /></label>
        <CategoryInput label="Category" />
        <label>Specifications or listing notes<textarea name="notes" rows={3} minLength={10} maxLength={3000} required /></label>
        <PriceFields label="Listed price" />
        <label>Public source URL<input type="url" name="source_url" maxLength={600} /></label>
        <Button type="submit" disabled={add.isPending}>{add.isPending ? "Saving…" : "Add device"}</Button>
      </form>
      </details>
      <ErrorNote error={catalog.error ?? add.error ?? remove.error} />
      {catalog.isPending ? <p role="status">Loading devices…</p>
        : catalog.data?.length ? <ul className="records-list advisor-sources">{catalog.data.map(item => <li key={item.id}>
          <Source item={item} />
          <Button variant="quiet" disabled={remove.isPending} onClick={() => remove.mutate(item.id)}
            aria-label={"Remove " + item.title}>Remove</Button>
        </li>)}</ul> : <p>No saved listings yet.</p>}
      {offset > 0 && <Button variant="quiet" onClick={() => setOffset(value => value - pageSize)}>Previous devices</Button>}
      {catalog.data?.length === pageSize && <LoadMore busy={catalog.isFetching} loading={false} onClick={() => setOffset(value => value + pageSize)} />}
    </section>
  </div>;
}

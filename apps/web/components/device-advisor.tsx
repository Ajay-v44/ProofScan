"use client";

import { api, apiDelete, ApiError, type AdvisorResult, type CatalogItem } from "@proofscan/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { LoadMore } from "./owner-collection";
import { ErrorNote, PublicShell } from "./shared";
import { Button } from "./ui/button";
import { AuthDialog } from "./workspace-forms";

const pageSize = 30;
const categories = [["phone", "Phone"], ["tablet", "Tablet"], ["laptop", "Laptop"], ["other", "Other"]];

function CategoryInput({ label }: { label: string }) {
  return <label>{label}<select name="category" defaultValue="phone">
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
    {item.price !== null && <span>{item.currency} {item.price.toLocaleString()}</span>}
    <p>{item.notes}</p>
    {item.source_url && <a className="quiet-link" href={item.source_url} rel="noreferrer">Open source</a>}
  </>;
}

export function DeviceAdvisor() {
  const [signIn, setSignIn] = useState(false);
  const session = useQuery({ queryKey: ["session"], queryFn: () => api<{ user_id: string }>("/auth/session") });
  const loggedOut = session.error instanceof ApiError && session.error.status === 401;

  return <PublicShell wide>
    <div className="page-title"><h1>Device advisor</h1>
      <p>Compare devices using the prices, specifications, and sources in your private catalog.</p></div>
    <ErrorNote error={loggedOut ? null : session.error} />
    {session.isPending && <p role="status">Opening your catalog…</p>}
    {loggedOut && <section className="panel form">
      <p>Sign in to use your private catalog.</p>
      <Button onClick={() => setSignIn(true)}>Sign in</Button>
    </section>}
    {signIn && !session.data && <AuthDialog initialRegister={false} onAuthenticated={() => setSignIn(false)} onClose={() => setSignIn(false)} />}
    {session.data && !session.isError && <AdvisorForms key={session.data.user_id} owner={session.data.user_id} />}
  </PublicShell>;
}

function AdvisorForms({ owner }: { owner: string }) {
  const client = useQueryClient();
  const [offset, setOffset] = useState(0);
  const listKey = ["advisor-catalog", owner] as const;
  const catalog = useQuery({
    queryKey: [...listKey, offset],
    queryFn: () => api<CatalogItem[]>("/agent/catalog?offset=" + offset),
  });
  const ask = useMutation({
    mutationFn: (data: FormData) => {
      const { amount, currency } = priceFields(data);
      return api<AdvisorResult>("/agent/ask", {
        question: String(data.get("question") ?? ""),
        category: String(data.get("category")),
        budget: amount, currency, allow_model: data.get("allow_model") === "on",
      });
    },
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

  return <div className="handoff-library">
    <section className="panel form">
      <h2>Ask a question</h2>
      <form className="form" onSubmit={event => {
        event.preventDefault();
        ask.mutate(new FormData(event.currentTarget));
      }}>
        <label>What are you looking for?<textarea name="question" rows={3} minLength={3} maxLength={600}
          placeholder="Which phone in my catalog should I consider for good battery life?" required /></label>
        <CategoryInput label="Device type" />
        <PriceFields label="Maximum budget" />
        <label className="check"><input type="checkbox" name="allow_model" />
          Allow Moonshot to use this question and relevant catalog excerpts for this answer.</label>
        <Button type="submit" disabled={ask.isPending}>{ask.isPending ? "Checking your catalog…" : "Get a recommendation"}</Button>
      </form>
      <ErrorNote error={ask.error} />
      {ask.data && <section className="form" aria-live="polite">
        <h3>{ask.data.status === "answer" ? "Recommendation" : ask.data.status === "needs_input" ? "One more detail" : "No matching evidence"}</h3>
        <p>{ask.data.message}</p>
        {ask.data.sources.length > 0 && <><h4>Sources from your catalog</h4>
          <ul className="records-list advisor-sources">{ask.data.sources.map(item => <li key={item.id}><Source item={item} /></li>)}</ul></>}
      </section>}
    </section>
    <section className="panel form">
      <h2>Your catalog</h2>
      <form className="form" onSubmit={save}>
        <label>Device name<input name="title" minLength={2} maxLength={120} required /></label>
        <CategoryInput label="Category" />
        <label>Specifications or listing notes<textarea name="notes" rows={3} minLength={10} maxLength={3000} required /></label>
        <PriceFields label="Listed price" />
        <label>Public source URL<input type="url" name="source_url" maxLength={600} /></label>
        <Button type="submit" disabled={add.isPending}>{add.isPending ? "Saving…" : "Add device"}</Button>
      </form>
      <ErrorNote error={catalog.error ?? add.error ?? remove.error} />
      {catalog.isPending ? <p role="status">Loading devices…</p>
        : catalog.data?.length ? <ul className="records-list advisor-sources">{catalog.data.map(item => <li key={item.id}>
          <Source item={item} />
          <Button variant="quiet" disabled={remove.isPending} onClick={() => remove.mutate(item.id)}
            aria-label={"Remove " + item.title}>Remove</Button>
        </li>)}</ul> : <p>No saved devices on this page.</p>}
      {offset > 0 && <Button variant="quiet" onClick={() => setOffset(value => value - pageSize)}>Previous devices</Button>}
      {catalog.data?.length === pageSize && <LoadMore busy={catalog.isFetching} loading={false} onClick={() => setOffset(value => value + pageSize)} />}
    </section>
  </div>;
}

"use client";

import { api, apiDelete, ApiError, type BuyerChatAnswer, type BuyerChatPrice, type CatalogItem } from "@proofscan/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowUp, MessageSquare, Plus, SlidersHorizontal } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { LoadMore } from "./owner-collection";
import { ErrorNote } from "./shared";
import { Dialog } from "./ui/dialog";
import { Button, buttonVariants } from "./ui/button";
import { WorkspaceFrame } from "./workspace-frame";
import { accountHref } from "./account-navigation";
import "./buyer-chat.css";

type Market = "IN" | "US" | "GB";
type Turn = { id: number; question: string; answer?: BuyerChatAnswer };
const markets = { IN: "India", US: "United States", GB: "United Kingdom" } as const;
const catalogPageSize = 30;

export function DeviceAdvisor() {
  const session = useQuery({ queryKey: ["session"], queryFn: () => api<{ user_id: string }>("/auth/session") });
  const loggedOut = session.error instanceof ApiError && session.error.status === 401;

  return <WorkspaceFrame page="Buyer chat">
    <div className="page-title"><h1>Buyer chat</h1></div>
    <ErrorNote error={loggedOut ? null : session.error} />
    {session.isPending && <p role="status">Opening chat…</p>}
    {loggedOut && <section className="panel form">
      <h2>Ask about ProofScan and your devices</h2>
      <p>Sign in to compare your shared reports, ask how checks work, or look up a device.</p>
      <Link className={buttonVariants()} href={accountHref("sign-in", "/advisor")}>Sign in</Link>
    </section>}
    {session.data && !session.isError && <Chat key={session.data.user_id} owner={session.data.user_id} />}
  </WorkspaceFrame>;
}

function Answer({ value }: { value: BuyerChatAnswer }) {
  return <div className="buyer-chat-answer">
    {value.message.split("\n\n").map((part, index) => <p key={index}>{part}</p>)}
    {value.pricing?.map(price => <PriceEvidence key={price.device} price={price} />)}
    {!!value.sources.length && <div className="buyer-chat-citations">
      <h3>Sources</h3>
      <ul>{value.sources.map((source, index) => <li key={`${source.kind}-${index}`}>
        <strong>{source.title}</strong>
        {source.detail && <p>{source.detail}</p>}
        {source.kind === "web" && source.href
          ? <PublicSource href={source.href} />
          : source.href && <Link className="quiet-link" href={source.href}>{source.kind === "report" ? "Open signed report" : "Open guide"}</Link>}
      </li>)}</ul>
    </div>}
    {value.checked_at && <p className="buyer-chat-time">Search checked <time dateTime={value.checked_at}>{new Date(value.checked_at).toLocaleString()}</time></p>}
  </div>;
}

function PriceEvidence({ price }: { price: BuyerChatPrice }) {
  const { current, launch } = price;
  const locale = { IN: "en-IN", GB: "en-GB", US: "en-US" }[price.market];
  const formatter = new Intl.NumberFormat(locale, { style: "currency", currency: price.currency, minimumFractionDigits: 0 });
  const amount = (minor: number) => formatter.format(minor / 100);
  const age = launch ? new Date().getUTCFullYear() - launch.year : 0;
  const percent = current && launch && current.storage_gb === launch.storage_gb
    ? Math.round(current.median_minor / launch.price_minor * 100)
    : null;

  if (!current && !launch) return null;
  return <section className="buyer-chat-price" aria-label={`Pricing for ${price.device}`}>
    <h3>{price.device} <span>{markets[price.market]}</span></h3>
    <dl>
      <div>
        <dt>Current asking-price estimate</dt>
        <dd>{current ? <>
          <strong>{amount(current.low_minor)}–{amount(current.high_minor)}</strong>
          <p>Median {amount(current.median_minor)} · {current.storage_gb} GB · {current.condition}</p>
          <p>Based on {current.merchant_count} retailers’ indexed listings.</p>
        </> : "Too few comparable listings"}</dd>
      </div>
      <div>
        <dt>Manufacturer launch price</dt>
        <dd>{launch ? <>
          <strong>{amount(launch.price_minor)}</strong>
          <p>{launch.year} starting price{launch.storage_gb ? ` · ${launch.storage_gb} GB` : ""}{age > 0 ? ` · about ${age} ${age === 1 ? "year" : "years"} ago` : ""}</p>
          <PublicSource href={launch.href} label="Read the launch announcement" />
        </> : "No verified launch price"}</dd>
      </div>
    </dl>
    {percent !== null && <p>Current median asking price is {percent}% of the launch price for the same storage.</p>}
  </section>;
}

function PublicSource({ href, label = "Open public source" }: { href: string; label?: string }) {
  const [copyState, setCopyState] = useState<"idle" | "copied" | "show-link">("idle");

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(href);
      setCopyState("copied");
    } catch {
      setCopyState("show-link");
    }
  }

  return <div className="buyer-chat-source-links">
    <a className="quiet-link" href={href} target="_blank" rel="noreferrer noopener">{label}</a>
    <Button variant="quiet" onClick={() => void copyLink()}>Copy link</Button>
    {copyState === "copied" && <span role="status">Link copied</span>}
    {copyState === "show-link" && <input aria-label="Public source address" readOnly value={href} onFocus={event => event.currentTarget.select()} />}
  </div>;
}

function Chat({ owner }: { owner: string }) {
  const composer = useRef<HTMLTextAreaElement>(null);
  const log = useRef<HTMLDivElement>(null);
  const sequence = useRef(0);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [options, setOptions] = useState(false);
  const [catalog, setCatalog] = useState(false);
  const [market, setMarket] = useState<Market>("IN");
  const [allowWeb, setAllowWeb] = useState(true);
  const [allowModel, setAllowModel] = useState(false);
  const [includeListings, setIncludeListings] = useState(false);
  const ask = useMutation({
    gcTime: 0,
    mutationFn: ({ question, history }: { id: number; question: string; history: string[] }) =>
      api<BuyerChatAnswer>("/agent/chat", { message: question, history, market,
        allow_web: allowWeb, allow_model: allowModel, include_listings: includeListings }),
    onSuccess: (answer, input) => setTurns(current => current.map(turn => turn.id === input.id ? { ...turn, answer } : turn)),
  });

  useEffect(() => {
    const thread = log.current;
    if (thread) thread.scrollTop = thread.scrollHeight;
  }, [turns, ask.isPending, ask.isError]);

  function submit(event: FormEvent) {
    event.preventDefault();
    const question = draft.trim();
    if (ask.isPending || !question) return;
    const id = sequence.current++;
    setTurns(current => [...current.slice(-39), { id, question }]);
    setDraft("");
    ask.mutate({ id, question, history: turns.filter(turn => turn.answer).slice(-4).map(turn => turn.question) });
  }

  return <section className="buyer-chat" aria-label="Buyer conversation">
    <header className="buyer-chat-header">
      <Button variant="outline" disabled={ask.isPending} onClick={() => { ask.reset(); setTurns([]); setDraft(""); composer.current?.focus(); }}>
        <Plus size={17} aria-hidden />New chat
      </Button>
      <div className="actions">
        <Button variant="quiet" onClick={() => setCatalog(true)}>Saved listings</Button>
        <Button variant="quiet" onClick={() => setOptions(true)}><SlidersHorizontal size={16} aria-hidden />Chat settings</Button>
      </div>
    </header>
    <div ref={log} className="buyer-chat-log" role="log" aria-label="Conversation" tabIndex={0}>
      {!turns.length && <div className="buyer-chat-empty">
        <span className="icon-tile"><MessageSquare aria-hidden size={23} /></span>
        <h2>What would you like to check?</h2>
        <p>Ask how ProofScan works, compare your shared reports, or look up a device you’re considering.</p>
      </div>}
      {turns.map(turn => <article className="buyer-chat-turn" key={turn.id}>
        <div className="buyer-chat-question"><span>You</span><p>{turn.question}</p></div>
        {turn.answer && <div className="buyer-chat-reply"><span>ProofScan</span><Answer value={turn.answer} /></div>}
      </article>)}
      {ask.isPending && <p className="buyer-chat-progress" role="status">Checking sources…</p>}
      {ask.isError && <div className="buyer-chat-failure">
        <ErrorNote error={ask.error} />
        {ask.variables && <Button variant="outline" onClick={() => { if (ask.variables) ask.mutate(ask.variables); }}>Retry answer</Button>}
      </div>}
    </div>
    <form className="buyer-chat-compose" onSubmit={submit}>
      <label htmlFor="buyer-chat-message" className="buyer-chat-sr-only">Ask ProofScan</label>
      <div className="buyer-chat-input">
        <textarea id="buyer-chat-message" ref={composer} value={draft} onChange={event => setDraft(event.target.value)}
          rows={2} maxLength={1000} placeholder="Ask about a device or ProofScan" onKeyDown={event => {
            if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
              event.preventDefault();
              if (!ask.isPending && draft.trim()) event.currentTarget.form?.requestSubmit();
            }
          }} />
        <Button type="submit" disabled={ask.isPending || !draft.trim()} aria-label="Send message"><ArrowUp size={19} aria-hidden /></Button>
      </div>
      <p>{allowWeb ? "Public search · " + markets[market] : "Public search off"} · Chat stays in this window</p>
    </form>
    {options && <Dialog title="Chat settings" onClose={() => setOptions(false)}><div className="dialog-form">
      <label>Default market<select value={market} onChange={event => setMarket(event.target.value as Market)}>
        {Object.entries(markets).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <label className="checkbox"><input type="checkbox" checked={allowWeb} onChange={event => setAllowWeb(event.target.checked)} />Allow public device search</label>
      <p>Public search uses the recognized device model and market. Your conversation and reports stay in ProofScan.</p>
      <label className="checkbox"><input type="checkbox" checked={includeListings} onChange={event => setIncludeListings(event.target.checked)} />Include my saved listings</label>
      <label className="checkbox"><input type="checkbox" checked={allowModel} onChange={event => setAllowModel(event.target.checked)} />Use Moonshot to select and review public evidence</label>
    </div></Dialog>}
    {catalog && <Dialog title="Saved listings" onClose={() => setCatalog(false)}><SavedListings owner={owner} /></Dialog>}
  </section>;
}

function SavedListings({ owner }: { owner: string }) {
  const client = useQueryClient();
  const [offset, setOffset] = useState(0);
  const key = ["advisor-catalog", owner] as const;
  const listing = useQuery({ queryKey: [...key, offset], queryFn: () => api<CatalogItem[]>("/agent/catalog?offset=" + offset) });
  const add = useMutation({
    mutationFn: (form: FormData) => api<CatalogItem>("/agent/catalog", {
      title: String(form.get("title")), category: form.get("category"), notes: String(form.get("notes")),
      price: form.get("price") ? Number(form.get("price")) : null,
      currency: String(form.get("currency") ?? "").trim() || null,
      source_url: String(form.get("source_url") ?? "").trim() || null,
    }),
    onSuccess: () => { setOffset(0); return client.invalidateQueries({ queryKey: key }); },
  });
  const remove = useMutation({
    mutationFn: (id: string) => apiDelete("/agent/catalog/" + id),
    onSuccess: () => {
      if (listing.data?.length === 1 && offset) setOffset(offset - catalogPageSize);
      return client.invalidateQueries({ queryKey: key });
    },
  });
  return <div className="dialog-form">
    <details><summary>Add a listing</summary><form className="form" onSubmit={event => {
      event.preventDefault();
      const form = event.currentTarget;
      add.mutate(new FormData(form), { onSuccess: () => form.reset() });
    }}>
      <label>Device name<input name="title" minLength={2} maxLength={120} required /></label>
      <label>Device type<select name="category"><option value="phone">Phone</option><option value="tablet">Tablet</option>
        <option value="laptop">Laptop</option><option value="other">Other</option></select></label>
      <label>Specifications or listing notes<textarea name="notes" minLength={10} maxLength={3000} required /></label>
      <div className="advisor-price"><label>Asking price<input name="price" type="number" min={1} max={100000000} /></label>
        <label>Currency<input name="currency" pattern="[A-Z]{3}" maxLength={3} placeholder="INR" /></label></div>
      <label>Public source URL<input name="source_url" type="url" maxLength={600} /></label>
      <Button type="submit" disabled={add.isPending}>Add device</Button>
    </form></details>
    <ErrorNote error={listing.error ?? add.error ?? remove.error} />
    {listing.isPending ? <p role="status">Loading listings…</p> : !listing.data?.length ? <p>No saved listings on this page.</p>
      : <ul className="records-list advisor-sources">{listing.data.map(item => <li key={item.id}><strong>{item.title}</strong>
        <p>{item.notes}</p><Button variant="quiet" disabled={remove.isPending} onClick={() => remove.mutate(item.id)}
          aria-label={"Remove " + item.title}>Remove</Button></li>)}</ul>}
    {offset > 0 && <Button variant="quiet" onClick={() => setOffset(offset - catalogPageSize)}>Previous listings</Button>}
    {listing.data?.length === catalogPageSize && <LoadMore busy={listing.isFetching} loading={false} onClick={() => setOffset(offset + catalogPageSize)} />}
  </div>;
}

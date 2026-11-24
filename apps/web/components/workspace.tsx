"use client";

import { api, ApiError, type Notification, type Report, type Verification } from "@proofscan/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bell, FileCheck2, FolderOpen, Grid2X2, Laptop,
  Ellipsis, Link2, List, LogOut, PackageCheck, Plus, RefreshCw, ScanLine, Search, ShieldCheck, Sparkles, UserRound,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent as ReactKeyboardEvent } from "react";
import { ReportDetails } from "./report";
import { LoadMore, useOwnerCollection } from "./owner-collection";
import { ErrorNote, Status } from "./shared";
import { Button, buttonVariants } from "./ui/button";
import { Dialog } from "./ui/dialog";
import { AuthDialog, NewVerification } from "./workspace-forms";
import { WorkspaceFrame, type WorkspaceSection } from "./workspace-frame";

type Session = { user_id: string; listing_assistance: boolean };
type Example = { id: string; label: string; detail: string; report: Report };
type Filter = "All" | "In progress" | "Shared" | "Closed";
type Overlay = "sign-in" | "register" | "new" | "seller" | "search" | "account" | null;

function example(id: string, label: string, manufacturer: string, model: string, storage: number): Example {
  const matches = storage === 512;
  return {
    id, label, detail: matches ? "3 listing checks match" : "2 listing checks match · 1 differs",
    report: {
      schema_version: 2, report_id: id, verification_id: id, label, captured_at: "", platform: "simulator",
      assurance: "SIMULATED", hardware: { manufacturer, model, memory_gib: 16, battery_health_percent: 92,
        cpu: ["Intel Core i5"], gpu: [], drives: [{ capacity_gb: storage }] },
      findings: [
        { metric: "Memory (GiB)", claimed: 16, observed: 16, status: "MATCH" },
        { metric: "Largest storage drive (GB)", claimed: 512, observed: storage, status: matches ? "MATCH" : "MISMATCH" },
        { metric: "Battery health (%)", claimed: 90, observed: 92, status: "MATCH" },
      ],
      identity_confidence: "UNAVAILABLE", pricing: "UNAVAILABLE",
    },
  };
}

const examples = [
  example("thinkpad", "ThinkPad T14 Gen 3", "Lenovo", "ThinkPad T14 Gen 3", 256),
  example("latitude", "Latitude 5440", "Dell", "Latitude 5440", 512),
];
const filters: Filter[] = ["All", "In progress", "Shared", "Closed"];
const closed = ["DECLINED", "EXPIRED", "CANCELLED", "FAILED"];

function rowFilter(status: string, filter: Filter) {
  if (filter === "Shared") return status === "COMPLETED";
  if (filter === "Closed") return closed.includes(status);
  if (filter === "In progress") return status !== "COMPLETED" && !closed.includes(status);
  return true;
}

const events: Record<string, string> = {
  SELLER_OPENED: "Seller opened your link", SCANNING: "Seller started scanning",
  REPORT_READY: "Seller preview is ready", SHARED: "Seller shared a signed report",
  DECLINED: "Seller declined to share", EXPIRED: "Request expired", CANCELLED: "Seller access was revoked",
  HANDOFF_REPORT_READY: "Handoff comparison is ready",
};

function VerificationDetails({ record }: { record: Verification }) {
  const order = ["LINK_CREATED", "SELLER_OPENED", "CONSENTED", "SCANNING", "SELLER_REVIEW", "COMPLETED"];
  const current = order.indexOf(record.status);
  const steps = [{ label: "Seller link created", at: 0 }, { label: "Seller opened the link", at: 1 },
    { label: "Device collection started", at: 3 }, { label: "Seller preview ready", at: 4 },
    { label: "Signed report shared", at: 5 }];
  return <div className="detail-body">
    <Status value={record.status} />
    <dl className="detail-metadata">
      <div><dt>Created</dt><dd>{new Date(record.created_at).toLocaleString()}</dd></div>
      <div><dt>Seller link expires</dt><dd>{new Date(record.expires_at).toLocaleString()}</dd></div>
    </dl>
    <ol className="record-progress" aria-label="Verification progress">{steps.map(item => <li
      data-reached={item.at === 0 || current >= item.at} key={item.label}><span />{item.label}</li>)}</ol>
    {record.status === "COMPLETED" && <Link href={"/reports/" + record.id} className={buttonVariants()}>Open report</Link>}
  </div>;
}

function Records({ rows, showExamples, pending, onExample, onRecord, onRefresh, onCreate }: {
  rows: Verification[]; showExamples: boolean; pending: boolean;
  onExample: (item: Example) => void; onRecord: (id: string) => void;
  onRefresh: () => void; onCreate: () => void;
}) {
  const [filter, setFilter] = useState<Filter>("All");
  const [view, setView] = useState<"list" | "grid">("list");
  const visible = rows.filter(item => rowFilter(item.status, filter));
  const samples = showExamples && (filter === "All" || filter === "Shared") ? examples : [];

  return <section className="library" aria-labelledby="recent-title">
    <header className="library-head">
      <div><h2 id="recent-title">{showExamples ? "Example verifications" : "Recent verifications"}</h2>
        {showExamples && <p>Open an example to see how a report compares listing claims with device readings.</p>}</div>
      <div className="library-actions">
        {!showExamples && <button className="icon-button" onClick={onRefresh} aria-label="Refresh"><RefreshCw size={17} aria-hidden /></button>}
        <div className="view-switch" role="group" aria-label="Display">
          <button className="icon-button" type="button" aria-label="List view" aria-pressed={view === "list"} onClick={() => setView("list")}><List size={18} aria-hidden /></button>
          <button className="icon-button" type="button" aria-label="Grid view" aria-pressed={view === "grid"} onClick={() => setView("grid")}><Grid2X2 size={16} aria-hidden /></button>
        </div>
      </div>
    </header>
    {!showExamples && <div className="filter-bar" role="group" aria-label="Filter verifications">{filters.map(value =>
      <button type="button" className="filter-button" key={value} aria-pressed={value === filter} onClick={() => setFilter(value)}>{value}</button>
    )}</div>}
    {pending ? <p className="empty" role="status">Loading verifications…</p>
      : visible.length + samples.length === 0 ? <div className="empty library-empty">
          <span className="icon-tile"><FolderOpen aria-hidden size={23} /></span>
          <strong>{filter === "All" ? "No verifications yet" : "No verifications in this view"}</strong>
          {filter === "All" ? <Button variant="outline" onClick={onCreate}>Create verification</Button>
            : <Button variant="quiet" onClick={() => setFilter("All")}>Show all</Button>}
        </div>
      : <ul className={"verification-collection collection-" + view}>
          {samples.map((item, index) => <li className="verification-item" key={item.id}>
            <button className="record-main" type="button" onClick={() => onExample(item)}>
              <span className={"device-thumb " + (index === 0 ? "thumb-lilac" : "thumb-mint")}><Laptop size={25} strokeWidth={1.65} aria-hidden /></span>
              <span className="record-text"><strong>{item.label}</strong><span>{item.detail}</span></span>
            </button>
            <div className="record-end"><span className="example-status">Example</span>
              <button type="button" className="text-action" onClick={() => onExample(item)}>View sample report</button></div>
          </li>)}
          {visible.map(row => <li className="verification-item" key={row.id}>
            <button type="button" className="record-main" onClick={() => onRecord(row.id)}>
              <span className="device-thumb thumb-lilac"><Laptop size={24} strokeWidth={1.65} aria-hidden /></span>
              <span className="record-text"><strong>{row.label}</strong><time dateTime={row.created_at}>{new Date(row.created_at).toLocaleDateString()}</time></span>
            </button>
            <div className="record-end"><Status value={row.status} />
              {row.status === "COMPLETED" ? <Link className="text-action" href={"/reports/" + row.id}>Open report</Link>
                : <button className="text-action" type="button" onClick={() => onRecord(row.id)}>View details</button>}</div>
          </li>)}
        </ul>}
  </section>;
}

function SellerLink() {
  const router = useRouter();
  const [error, setError] = useState("");
  function open(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const source = String(new FormData(event.currentTarget).get("seller-link") ?? "").trim();
    try {
      const url = new URL(source, window.location.origin);
      if (url.origin !== window.location.origin || url.username || url.password ||
          !/^\/seller\/[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i.test(url.pathname)
          || !/^#[A-Za-z0-9_-]{43}$/.test(url.hash)) {
        throw new Error();
      }
      router.push(url.pathname + url.hash);
    } catch { setError("Paste the original ProofScan seller link for this workspace."); }
  }
  return <form className="dialog-form" onSubmit={open}>
    <p>Use the private link a buyer sent you. You can review the readings before sharing them.</p>
    <label>Seller link<input data-dialog-autofocus name="seller-link" placeholder="Paste your private link" autoComplete="off" required /></label>
    <ErrorNote error={error && new Error(error)} />
    <Button type="submit">Open verification</Button>
  </form>;
}

function SearchWorkspace({ rows, onExample, onRecord, onCreate, onSeller }: {
  rows: Verification[]; onExample: (item: Example) => void; onRecord: (id: string) => void;
  onCreate: () => void; onSeller: () => void;
}) {
  const [query, setQuery] = useState("");
  const results = useRef<HTMLDivElement>(null);
  const value = query.trim().toLowerCase();
  const actions = [
    { name: "New verification", icon: ScanLine, onClick: onCreate },
    { name: "Open a seller link", icon: Link2, onClick: onSeller },
  ].filter(item => item.name.toLowerCase().includes(value));
  const links = [
    { name: "Handoffs", icon: PackageCheck, href: "/handoffs" },
    { name: "Check a report", icon: ShieldCheck, href: "/verify" },
    { name: "Buyer chat", icon: Sparkles, href: "/advisor" },
  ].filter(item => item.name.toLowerCase().includes(value));
  const real = rows.filter(item => (item.label + " " + item.id).toLowerCase().includes(value)).slice(0, 8);
  const samples = examples.filter(item => item.label.toLowerCase().includes(value));
  function navigate(event: ReactKeyboardEvent<HTMLDivElement>) {
    const items = Array.from(results.current?.querySelectorAll<HTMLElement>("button, a") ?? []);
    if (!items.length) return;
    if (event.key === "Enter" && value && event.target instanceof HTMLInputElement) {
      event.preventDefault(); items[0].click(); return;
    }
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
    event.preventDefault();
    const current = items.findIndex(item => item === document.activeElement);
    if (current < 0) items[event.key === "ArrowDown" ? 0 : items.length - 1].focus();
    else items[(current + (event.key === "ArrowDown" ? 1 : items.length - 1)) % items.length].focus();
  }
  return <div className="search-dialog-body" onKeyDown={navigate}>
    <label className="search-field"><Search size={19} aria-hidden /><input data-dialog-autofocus aria-label="Search verifications and tools" value={query}
      onChange={event => setQuery(event.target.value)} placeholder="Search verifications and tools" /></label>
    <div className="search-results" ref={results}>
      {actions.map(({ name, icon: Icon, onClick }) => <button key={name} onClick={onClick}><Icon size={18} aria-hidden />{name}</button>)}
      {links.map(({ name, icon: Icon, href }) => <Link href={href} key={name}><Icon size={18} aria-hidden />{name}</Link>)}
      {real.map(item => <button key={item.id} onClick={() => onRecord(item.id)}><Laptop size={18} aria-hidden />{item.label}</button>)}
      {samples.map(item => <button key={item.id} onClick={() => onExample(item)}><FileCheck2 size={18} aria-hidden />{item.label}<small>Example</small></button>)}
      {!actions.length && !links.length && !real.length && !samples.length && <p role="status">No matches. Try a device name or a tool.</p>}
    </div>
  </div>;
}

export function Workspace({ initialSection, initialOverlay }: { initialSection: WorkspaceSection; initialOverlay: "search" | "seller" | null }) {
  const client = useQueryClient();
  const [section, setSection] = useState(initialSection);
  const [overlay, setOverlay] = useState<Overlay>(initialOverlay);
  const [sample, setSample] = useState<Example | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [afterSignIn, setAfterSignIn] = useState(false);
  const session = useQuery({ queryKey: ["session"], queryFn: () => api<Session>("/auth/session") });
  const user = session.data;
  const rows = useOwnerCollection<Verification>("/verifications", "verifications", user?.user_id, { pollInterval: 7500 });
  const activity = useOwnerCollection<Notification>("/notifications", "activity", user?.user_id, {
    enabled: section === "Activity", pollInterval: 7500,
  });
  const logout = useMutation({ mutationFn: () => api("/auth/logout", {}),
    onSuccess: () => { client.clear(); window.location.reload(); } });
  const sessionError = session.error instanceof ApiError && session.error.status === 401 ? null : session.error;
  const current = rows.items.find(row => row.id === selected);
  const authOpen = overlay === "sign-in" || overlay === "register";

  useEffect(() => {
    function shortcut(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setSample(null);
        setSelected(null);
        setOverlay(current => current ? null : "search");
      }
    }
    window.addEventListener("keydown", shortcut);
    return () => window.removeEventListener("keydown", shortcut);
  }, []);

  function close() { setOverlay(null); setAfterSignIn(false); }
  function create() {
    if (user) { setAfterSignIn(false); setOverlay("new"); }
    else { setAfterSignIn(true); setOverlay("sign-in"); }
  }
  function viewExample(item: Example) { close(); setSelected(null); setSample(item); }
  function viewRecord(id: string) { close(); setSample(null); setSelected(id); }

  return <>
    <WorkspaceFrame page={section} onSectionChange={setSection}
      sidebarActions={<>
        <button type="button" className="nav-link" onClick={() => setOverlay("seller")}><Link2 size={18} aria-hidden />Open a seller link</button>
        {user ? <button type="button" className="nav-link" onClick={() => logout.mutate()} disabled={logout.isPending}><LogOut size={18} aria-hidden />Sign out</button>
          : <button type="button" className="nav-link" onClick={() => setOverlay("register")}><UserRound size={18} aria-hidden />Create an account</button>}
      </>}
      lead={<button type="button" className="workspace-search" onClick={() => setOverlay("search")} aria-label="Search workspace">
        <Search size={18} aria-hidden /><span>Search verifications or tools</span><kbd>Ctrl K</kbd></button>}
      actions={<>
          {user ? <>
            <Button className="top-new" onClick={create} aria-label="New verification"><Plus size={17} aria-hidden /><span>New verification</span></Button>
          </>
            : <Button variant="outline" onClick={() => setOverlay("sign-in")}>Sign in</Button>}
          <button type="button" className="icon-button top-account" aria-label="Workspace options" onClick={() => setOverlay("account")}><Ellipsis size={21} aria-hidden /></button>
      </>}>
        <ErrorNote error={sessionError ?? logout.error ?? rows.error ?? activity.error} />
        <div className="work-title">
          <h1>{section === "Home" ? "Your workspace" : section}</h1>
          <p>{section === "Home" ? "Check a device before buying, selling or handing it over."
            : section === "Verifications" ? "Track your requests and open the reports sellers have shared."
              : "See updates to your verifications and handoffs."}</p>
        </div>
        {section === "Home" && <section className="workspace-start" aria-label="Start a check">
          <div className="workspace-hero">
            <div className="hero-copy">
              <h2>Verify a purchase</h2>
              <p>Collect device readings and exterior photos in a signed report before you buy.</p>
              <Button onClick={create}>Start a verification</Button>
            </div>
          </div>
          <div className="quick-links">
            <Link className="quick-link" href="/handoffs"><span className="icon-tile"><PackageCheck size={21} aria-hidden /></span>
              <span><strong>Protect a handoff</strong><small>Compare condition at checkout and return.</small></span></Link>
            <Link className="quick-link" href="/advisor"><span className="icon-tile"><Sparkles size={21} aria-hidden /></span>
              <span><strong>Compare devices</strong><small>Ask Buyer Chat about reports shared with you.</small></span></Link>
          </div>
        </section>}
        {section !== "Activity" ? <>
          <Records key={String(!!user)} rows={rows.items} showExamples={!user}
            pending={!!user && rows.isPending} onExample={viewExample} onRecord={viewRecord}
            onRefresh={() => void rows.refetch()} onCreate={create} />
          {rows.hasNextPage && <LoadMore onClick={() => void rows.fetchNextPage()}
            busy={rows.isFetching} loading={rows.isFetchingNextPage} />}
        </>
          : <section className="library" aria-label="Request activity">
            {!user ? <div className="empty library-empty"><span className="icon-tile"><Bell size={22} aria-hidden /></span>
              <strong>Sign in to see your activity</strong><Button variant="outline" onClick={() => setOverlay("sign-in")}>Sign in to view activity</Button></div>
              : activity.isPending ? <p className="empty" role="status">Loading activity…</p>
                : !activity.items.length ? <p className="empty">No activity yet.</p>
                  : <ul className="records-list">{activity.items.map(item => <li key={item.id}>
                    <Bell size={17} aria-hidden /><strong>{events[item.event] ?? item.event}</strong>
                    <time dateTime={item.created_at}>{new Date(item.created_at).toLocaleString()}</time>
                    {item.handoff_id && <Link className="quiet-link" href={"/handoffs/" + item.handoff_id}>Open comparison</Link>}
                  </li>)}</ul>}
            {activity.hasNextPage && <LoadMore onClick={() => void activity.fetchNextPage()}
              busy={activity.isFetching} loading={activity.isFetchingNextPage} />}
          </section>}
    </WorkspaceFrame>
    {overlay === "new" && user && <Dialog title="New verification" onClose={close}>
      <NewVerification listingAssistance={user.listing_assistance} onClose={() => { setSection("Verifications"); close(); }} />
    </Dialog>}
    {authOpen && !user && <AuthDialog key={overlay} initialRegister={overlay === "register"} onClose={close} onAuthenticated={() => {
        if (afterSignIn) { setAfterSignIn(false); setOverlay("new"); }
        else close();
      }} />}
    {overlay === "seller" && <Dialog title="Open a seller link" onClose={close}><SellerLink /></Dialog>}
    {overlay === "account" && <Dialog title="Workspace options" onClose={close}>
      <div className="dialog-form"><ErrorNote error={logout.error} />
        <div className="search-results">
          <button type="button" onClick={() => setOverlay("seller")}>Open a seller link</button>
          <button type="button" onClick={() => { setSection("Activity"); close(); }}>Activity</button>
          <Link href="/verify">Check a report</Link>
          <Link href="/about">About ProofScan</Link>
          <Link href="/help">Help</Link>
          {user ? <button type="button" onClick={() => logout.mutate()} disabled={logout.isPending}>Sign out</button>
            : <button type="button" onClick={() => setOverlay("register")}>Create an account</button>}
        </div>
      </div>
    </Dialog>}
    {overlay === "search" && <Dialog title="Search workspace" onClose={close}>
      <SearchWorkspace rows={rows.items} onCreate={create} onExample={viewExample} onRecord={viewRecord} onSeller={() => setOverlay("seller")} />
    </Dialog>}
    {sample && <Dialog title={sample.label} placement="side" onClose={() => setSample(null)}><div className="detail-body">
      <ReportDetails report={sample.report} photoPath="" /></div></Dialog>}
    {current && <Dialog title={current.label} placement="side" onClose={() => setSelected(null)}><VerificationDetails record={current} /></Dialog>}
  </>;
}

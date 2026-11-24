import { Bell, CircleHelp, ClipboardList, FileCheck2, House, MessagesSquare, PackageCheck, Search, ShieldCheck } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { Brand, ProductFooter } from "./shared";

export type WorkspaceSection = "Home" | "Verifications" | "Activity";
type WorkspacePage = WorkspaceSection | "Handoffs" | "Buyer chat" | "Operator" | "Purchase report";

const destinations = [
  { name: "Home", href: "/", Icon: House, section: "Home", compact: true },
  { name: "Verifications", href: "/?view=verifications", Icon: ClipboardList, section: "Verifications", compact: true },
  { name: "Handoffs", href: "/handoffs", Icon: PackageCheck, section: null, compact: true },
  { name: "Buyer chat", href: "/advisor", Icon: MessagesSquare, section: null, compact: true },
  { name: "Activity", href: "/?view=activity", Icon: Bell, section: "Activity", compact: false },
  { name: "Check a report", href: "/verify", Icon: ShieldCheck, section: null, compact: false },
] as const;

export function WorkspaceFrame({ page, onSectionChange, lead, actions, sidebarActions, admin, children }: {
  page: WorkspacePage; onSectionChange?: (section: WorkspaceSection) => void; lead?: ReactNode;
  actions?: ReactNode; sidebarActions?: ReactNode; admin?: boolean; children: ReactNode;
}) {
  return <div className="workspace">
    <a className="skip-link" href="#main">Skip to content</a>
    <aside className="sidebar">
      <div className="sidebar-brand"><Brand /></div>
      <nav className="navigation" aria-label="Workspace">
        {destinations.map(({ name, href, Icon, section, compact }) => {
          const active = page === name || (page === "Purchase report" && section === "Verifications");
          const item = { className: "nav-link" + (compact ? "" : " nav-desktop"), "aria-current": active ? "page" as const : undefined };
          const content = <><Icon size={19} aria-hidden /><span>{name}</span></>;
          return section && onSectionChange
            ? <button type="button" key={name} {...item} onClick={() => onSectionChange(section)}>{content}</button>
            : <Link href={href} key={name} {...item}>{content}</Link>;
        })}
        {(admin || page === "Operator") && <Link className="nav-link nav-desktop" href="/admin" aria-current={page === "Operator" ? "page" : undefined}>
          <FileCheck2 size={19} aria-hidden /><span>Operator</span></Link>}
      </nav>
      <div className="sidebar-footer">
        <Link className="nav-link" href="/about"><CircleHelp size={19} aria-hidden /><span>About &amp; support</span></Link>
        {sidebarActions}
      </div>
    </aside>
    <div className="workspace-main">
      <header className="workspace-header">
        <div className="workspace-header-inner">
          <div className="mobile-brand"><Brand /></div>
          <div className="workspace-location" aria-label="Current section">{page === "Home" ? "Overview" : page}</div>
          {lead ?? <Link href="/?action=search" className="workspace-search" aria-label="Search workspace"><Search size={18} aria-hidden /><span>Search workspace</span><kbd>Ctrl K</kbd></Link>}
          <div className="top-actions">{actions ?? <>
            <Link className="icon-button compact-report" href="/verify" aria-label="Check a report"><ShieldCheck size={20} aria-hidden /></Link>
            <Link className="icon-button" href="/help" aria-label="Help"><CircleHelp size={20} aria-hidden /></Link>
          </>}</div>
        </div>
      </header>
      <main id="main" tabIndex={-1} className="workspace-body">{children}</main>
      <ProductFooter />
    </div>
  </div>;
}

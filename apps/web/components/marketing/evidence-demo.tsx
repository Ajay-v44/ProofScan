"use client";

import { FileCheck2 } from "lucide-react";
import { useId, useRef, useState, type KeyboardEvent } from "react";

const scenarios = [
  { label: "Before buying", title: "Laptop purchase check", columns: ["Listing", "Collected"],
    rows: [
      { name: "Memory", before: "16 GiB", after: "16 GiB" },
      { name: "Largest drive", before: "512 GB", after: "256 GB", review: true },
      { name: "Battery health", before: "90% minimum", after: "92%" },
    ], result: "Storage differs from the listing.", detail: "Ask the seller about the drive before deciding what to pay." },
  { label: "At pickup", title: "Pickup recheck", columns: ["Original", "At pickup"],
    rows: [
      { name: "Reported memory", before: "16 GiB", after: "8 GiB", review: true },
      { name: "Largest drive", before: "512 GB", after: "512 GB" },
      { name: "Front photo", before: "Saved", after: "Saved" },
    ], result: "The memory reading changed.", detail: "Check the device in hand and compare both reports before accepting it." },
  { label: "At return", title: "Equipment handoff", columns: ["At checkout", "At return"],
    rows: [
      { name: "Front view", before: "Saved", after: "Saved" },
      { name: "Left side", before: "No visible wear", after: "Review photo", review: true },
      { name: "Return condition", before: "Recorded", after: "Recorded" },
    ], result: "One view needs a closer look.", detail: "Compare photos taken from the same angle and inspect the item in person." },
] as const;

export function EvidenceDemo() {
  const id = useId();
  const tabs = useRef<(HTMLButtonElement | null)[]>([]);
  const [selection, setSelection] = useState(0);
  const report = scenarios[selection];

  function navigate(event: KeyboardEvent<HTMLButtonElement>) {
    const last = scenarios.length - 1;
    let next: number;
    switch (event.key) {
      case "ArrowLeft": next = selection === 0 ? last : selection - 1; break;
      case "ArrowRight": next = selection === last ? 0 : selection + 1; break;
      case "Home": next = 0; break;
      case "End": next = last; break;
      default: return;
    }
    event.preventDefault();
    setSelection(next);
    tabs.current[next]?.focus();
  }

  return <div className="pitch-demo">
    <div className="pitch-demo-tabs" role="tablist" aria-label="Report examples">
      {scenarios.map(({ label }, index) => <button key={label} type="button" role="tab"
        id={id + "-tab-" + index} aria-controls={id + "-report"} aria-selected={index === selection} tabIndex={index === selection ? 0 : -1}
        ref={node => { tabs.current[index] = node; }} onClick={() => setSelection(index)} onKeyDown={navigate}>{label}</button>)}
    </div>
    <div className="pitch-demo-report" role="tabpanel" tabIndex={0} id={id + "-report"} aria-labelledby={id + "-tab-" + selection}>
      <div className="pitch-demo-heading">
        <span className="pitch-demo-mark"><FileCheck2 size={22} aria-hidden /></span>
        <div><h3>{report.title}</h3><p>Illustrative report</p></div>
      </div>
      <table>
        <thead><tr><th scope="col">Evidence</th>{report.columns.map(column => <th scope="col" key={column}>{column}</th>)}</tr></thead>
        <tbody>{report.rows.map(row => <tr key={row.name} className={"review" in row ? "needs-review" : undefined}>
          <th scope="row">{row.name}</th><td>{row.before}</td><td>{row.after}</td>
        </tr>)}</tbody>
      </table>
      <div className="pitch-demo-result"><strong>{report.result}</strong><p>{report.detail}</p></div>
    </div>
  </div>;
}

import "@fontsource-variable/manrope";
import { themeVariables } from "@proofscan/design-tokens";
import { invoke } from "@tauri-apps/api/core";
import { CircleCheck, Download, LayoutGrid, ScanLine, Upload } from "lucide-react";
import { useState, type CSSProperties } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";

type Scan = { hardware: { manufacturer: string | null; model: string | null; memory_gib: number | null; cpu: string[] }; challenge: string };

function Collector() {
  const [ticket, setTicket] = useState<File | null>(null);
  const [result, setResult] = useState<Scan | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);

  function choose(file: File | null) {
    setTicket(file);
    setResult(null);
    setError("");
  }

  async function collect() {
    if (!ticket) return;
    setError("");
    setResult(null);
    setBusy(true);
    try {
      if (ticket.size > 4096) throw new Error("The scan ticket is too large.");
      setResult(await invoke<Scan>("collect_hardware", { ticket: await ticket.text() }));
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : String(failure));
    } finally {
      setBusy(false);
    }
  }

  function exportScan() {
    if (!result) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(result)], { type: "application/json" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "proofscan-scan.json";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  async function workspace() {
    try { await invoke("show_workspace"); }
    catch (failure) { setError(failure instanceof Error ? failure.message : String(failure)); }
  }

  return <div className="desktop" style={themeVariables as CSSProperties}>
    <header className="topbar">
      <span className="brand"><span className="brand-mark"><ScanLine size={20} aria-hidden /></span>ProofScan</span>
      <button className="quiet" type="button" onClick={() => void workspace()}><LayoutGrid size={17} aria-hidden />Workspace</button>
    </header>
    <main>
      <div className="intro"><h1>Device scanner</h1><p>Use the scan ticket from your seller page to collect readings on this device.</p></div>
      <ol className="steps" aria-label="Scanner progress">
        {["Load ticket", "Collect readings", "Export scan"].map((label, index) => <li key={label}
          aria-current={index === (result ? 2 : ticket ? 1 : 0) ? "step" : undefined}><span>{index + 1}</span>{label}</li>)}
      </ol>
      <section className="card">
        <h2>Scan ticket</h2>
        <label className="file-area" data-dragging={dragging} onDragOver={event => {
          event.preventDefault();
          if (!busy) setDragging(true);
        }} onDragLeave={() => setDragging(false)} onDrop={event => {
          event.preventDefault(); setDragging(false);
          if (!busy) choose(event.dataTransfer.files[0] ?? null);
        }}>
          <Upload size={19} aria-hidden />
          <span>{ticket?.name ?? "Choose or drop a ticket file"}</span>
          <input type="file" accept=".json,application/json" disabled={busy} aria-label="Scan ticket"
            onChange={event => choose(event.target.files?.[0] ?? null)} />
        </label>
        <button type="button" disabled={!ticket || busy} onClick={() => void collect()}>{busy ? "Collecting…" : "Collect hardware readings"}</button>
      </section>
      {error && <p role="alert" className="error">{error}</p>}
      {result && <section className="card" aria-live="polite">
        <div className="success"><CircleCheck size={19} aria-hidden /><h2>Scan ready</h2></div>
        <p>{[result.hardware.manufacturer, result.hardware.model].filter(Boolean).join(" ")} {result.hardware.memory_gib && " · " + result.hardware.memory_gib + " GiB memory"}</p>
        <p>Upload the exported scan to your seller page to review it.</p>
        <button type="button" onClick={exportScan}><Download size={17} aria-hidden />Export scan</button>
      </section>}
    </main>
  </div>;
}

createRoot(document.getElementById("root")!).render(<Collector />);

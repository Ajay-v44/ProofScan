import { BatteryCharging, Cpu, HardDrive, MemoryStick } from "lucide-react";
import type { Report } from "@proofscan/api-client";
import { Status } from "./shared";
import { checkLabels } from "./functional-checks";
import { EvidenceGallery } from "./evidence-gallery";

export function ReportDetails({ report, photoPath }: { report: Report; photoPath: string }) {
  const hardware = report.hardware;
  const device = { windows: "Windows", macos: "macOS", android: "Android", ios: "iOS", simulator: "Simulator" }[report.platform];
  const price = report.price_estimate;
  const format = price ? new Intl.NumberFormat(undefined, { style: "currency", currency: price.currency, maximumFractionDigits: 0 }) : null;
  const differences = report.findings.filter(item => item.status === "MISMATCH").length;
  const matching = report.findings.filter(item => item.status === "MATCH").length;
  const unavailable = report.findings.length - matching - differences;
  return <>
    <div className={report.assurance === "SIMULATED" ? "notice warning" : "notice"}>
      {report.assurance === "SIMULATED" ? "SIMULATED DATA · For demonstration only." : device + " collector reading · Independent hardware attestation unavailable."}
    </div>
    {!!report.findings.length && <div className="report-result">
      <div><strong>{differences > 0 ? differences + (differences === 1 ? " listing difference" : " listing differences")
        : matching > 0 ? "Available readings match" : "Checks unavailable"}</strong>
        <p>{matching} matched{unavailable > 0 ? " · " + unavailable + " unavailable" : ""}</p></div>
    </div>}
    <div className="metrics">
      {[
        { label: "Memory", value: hardware.memory_gib ? hardware.memory_gib + " GiB" : "Unavailable", Icon: MemoryStick },
        { label: "Largest drive", value: hardware.drives.length ? Math.max(...hardware.drives.map(drive => drive.capacity_gb)) + " GB" : "Unavailable", Icon: HardDrive },
        { label: "Battery health", value: hardware.battery_health_percent == null ? "Unavailable" : hardware.battery_health_percent + "%", Icon: BatteryCharging },
        { label: "Processor", value: hardware.cpu[0] ?? "Unavailable", Icon: Cpu },
      ].map(({ label, value, Icon }) => <div className="metric" key={label}><Icon aria-hidden size={18} /><span>{label}</span><strong>{value}</strong></div>)}
    </div>
    {report.findings.length > 0 && <div className="table-scroll"><table>
      <caption>Listing claim comparison</caption>
      <thead><tr><th scope="col">Check</th><th scope="col">Claimed</th><th scope="col">Observed</th><th scope="col">Result</th></tr></thead>
      <tbody>{report.findings.map(finding => <tr key={finding.metric}><th scope="row">{finding.metric}</th><td>{finding.claimed}</td><td>{finding.observed ?? "Unavailable"}</td><td><Status value={finding.status} /></td></tr>)}</tbody>
    </table></div>}
    {!!report.functional?.length && <div className="table-scroll"><table>
      <caption>Functional checks</caption>
      <thead><tr><th scope="col">Check</th><th scope="col">Result</th><th scope="col">Source</th></tr></thead>
      <tbody>{report.functional.map(check => <tr key={check.test}><th scope="row">{checkLabels[check.test]}</th>
        <td>{check.result === "PASS" ? "Passed" : "Issue reported"}</td><td>{check.source === "SIMULATED" ? "Simulated" : "Seller observation"}</td>
      </tr>)}</tbody>
    </table></div>}
    {!!report.visual_evidence?.length && <div>
      <h2>Exterior photos</h2>
      <EvidenceGallery items={report.visual_evidence.map(photo => ({
        href: "/api/v1" + photoPath + "/" + photo.id, label: "Open " + photo.angle + " photo",
        width: photo.width, height: photo.height,
      }))} />
    </div>}
    {!!report.inspection_requests?.length && <details><summary>Evidence still missing</summary><ul>
      {report.inspection_requests.map(request => <li key={request.angle ?? request.test}>
        {request.angle ? "Exterior photo of the " + request.angle : "Battery health reading"}
      </li>)}
    </ul></details>}
    <details><summary>Technical details</summary><dl className="technical">
      <dt>Reported device</dt><dd>{[hardware.manufacturer, hardware.model].filter(Boolean).join(" ") || "Unavailable"}</dd>
      <dt>Graphics</dt><dd>{hardware.gpu.join(", ") || "Unavailable"}</dd>
      <dt>Device identity</dt><dd>Unavailable</dd>
      <dt>Market pricing</dt><dd>{price && format
        ? format.formatRange(price.low, price.high) + (price.source === "SIMULATED" ? " · Demo fixture" : " · " + price.sample_size + " recent comparables")
        : "Unavailable"}</dd>
    </dl></details>
  </>;
}

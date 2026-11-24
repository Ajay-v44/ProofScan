import type { Metadata } from "next";
import Link from "next/link";
import { PublicShell } from "../../components/shared";

export const metadata: Metadata = { title: "ProofScan help" };

export default function HelpPage() {
  return <PublicShell>
    <div className="page-title"><h1>Help with ProofScan</h1><p>Find your next step when checking a device or reading a report.</p></div>
    <div className="panel form product-copy">
      <section><h2>Open a seller link</h2><p>Keep the complete link, including its private code, and open it on the device being checked. For an expired link, ask the buyer to create a new verification.</p><Link className="quiet-link" href="/?action=seller">Open a seller link</Link></section>
      <section><h2>Take photos of a phone</h2><p>In the app scanner, share a camera link with a second phone or tablet. Use it to take the front and back photos, then refresh the photos on the original device.</p></section>
      <section><h2>Check a report signature</h2><p>Look up the report ID to check its signature and current validity. Use the private report in your workspace to see the readings and photos.</p><Link className="quiet-link" href="/verify">Check a report</Link></section>
      <section><h2>Keep evidence private</h2><p>Avoid faces, addresses, serial labels, and private documents in your photos. Share seller and camera links only with the people helping with that verification.</p><Link className="quiet-link" href="/privacy">Read about privacy</Link></section>
    </div>
  </PublicShell>;
}

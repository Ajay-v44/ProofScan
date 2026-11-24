import type { Metadata } from "next";
import { PublicShell } from "../../components/shared";

export const metadata: Metadata = { title: "Privacy in ProofScan" };

export default function PrivacyPage() {
  return <PublicShell>
    <div className="page-title"><h1>Privacy in ProofScan</h1><p>How device readings, photos and report sharing work in the app.</p></div>
    <div className="panel form product-copy">
      <section><h2>What a check collects</h2><p>ProofScan collects the supported device readings shown during consent. A new purchase check includes exterior photos. Keep faces, documents and private labels out of the frame.</p></section>
      <section><h2>What gets shared</h2><p>Sellers can review the purchase report before sharing it. A shared report is available to the buyer. Checking a signature by report ID shows validity information and keeps detailed readings and photos private.</p></section>
      <section><h2>Photo retention</h2><p>Private photos and their visual descriptors expire according to the workspace’s retention settings. Signed reports preserve the recorded findings and photo digests.</p></section>
      <section><h2>Buyer Chat</h2><p>Buyer Chat uses your shared reports by default. Optional Moonshot comparisons use structured data about the devices, prices and recognized preferences. The ProofScan operator dashboard shows aggregate agent usage.</p></section>
    </div>
  </PublicShell>;
}

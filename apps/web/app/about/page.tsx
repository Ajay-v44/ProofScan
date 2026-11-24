import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { PublicShell } from "../../components/shared";
import { buttonVariants } from "../../components/ui/button";
import { version } from "../../package.json";

export const metadata: Metadata = { title: "About ProofScan" };

export default function AboutPage() {
  return <PublicShell>
    <div className="page-title"><h1>About ProofScan</h1><p>ProofScan helps you document a device before you buy, sell, or hand it over.</p></div>
    <section className="panel form product-hero">
      <div className="product-version">
        <Image src="/brand/proofscan-mark.webp" width={52} height={52} alt="" unoptimized />
        <div><h2>ProofScan</h2><p>Web version {version}</p></div>
      </div>
      <div className="product-copy">
        <section><h3>Purchase checks</h3><p>Compare listing claims with available device readings and exterior photos. Sellers review the evidence before choosing whether to share it.</p></section>
        <section><h3>Handoffs and pickup</h3><p>Record the starting condition, then look for changes using new readings and photos. A signed report preserves the recorded evidence. Inspect the device in person before accepting it.</p></section>
      </div>
      <div className="actions"><Link className={buttonVariants({ variant: "outline" })} href="/help">Get help</Link><Link className="quiet-link" href="/privacy">How ProofScan handles your data</Link></div>
    </section>
  </PublicShell>;
}

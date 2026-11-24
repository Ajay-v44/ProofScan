import { Camera, Check, Download, Laptop2, Link2, Monitor, Smartphone } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { version } from "../../package.json";
import { Brand } from "../shared";
import { EvidenceDemo } from "./evidence-demo";
import { downloadUrls, siteSchema } from "./site-config";
import "./pitch.css";

const steps = [
  { title: "Send a private link", detail: "The buyer starts a check with the listing details. The seller opens the link and chooses whether to collect evidence.", Icon: Link2 },
  { title: "Capture the device", detail: "Collect available hardware readings and photograph the exterior. Use a second phone or tablet to photograph a phone being checked.", Icon: Camera },
  { title: "Compare before paying", detail: "The seller reviews the report before sharing. The buyer can check mismatches and compare fresh evidence at pickup.", Icon: Check },
];

const clients = [
  { name: "Windows", note: "Collect hardware readings from the device under inspection.", Icon: Monitor,
    href: downloadUrls.windows ?? "/collect-windows.ps1", action: downloadUrls.windows ? "Download for Windows" : "Download PowerShell collector", localFile: !downloadUrls.windows },
  { name: "macOS", note: downloadUrls.mac ? "Collect supported Mac hardware readings." : "The Mac collector is available for development. Signed installer pending.",
    Icon: Laptop2, href: downloadUrls.mac ?? "/help#desktop", action: downloadUrls.mac ? "Download for Mac" : "Desktop setup" },
  { name: "Android", note: downloadUrls.android ? "Run the mobile scanner and guide a second camera." : "Native mobile scanner. Public download pending.",
    Icon: Smartphone, href: downloadUrls.android ?? "/help#mobile", action: downloadUrls.android ? "Get the Android app" : "Mobile setup" },
  { name: "iPhone and iPad", note: downloadUrls.ios ? "Run the mobile scanner and review evidence in the app." : "Native mobile scanner. App Store listing pending.",
    Icon: Smartphone, href: downloadUrls.ios ?? "/help#mobile", action: downloadUrls.ios ? "Get the iOS app" : "Mobile setup" },
];

const questions = [
  { question: "Can I check a device again at pickup?", answer: "Yes. Start a pickup recheck from the signed report, collect new readings and photos, and compare the two reports. Inspect the device in person before accepting it." },
  { question: "What does a signed report prove?", answer: "The signature lets you check that the report is intact and still valid. Readings and photos help you assess a device’s condition. They cannot establish the identity of the physical unit on their own." },
  { question: "Who can see the readings and photos?", answer: "The seller decides whether to share a purchase report. If shared, the buyer can see the detailed evidence in their workspace. The public signature lookup shows integrity and validity information." },
  { question: "Can ProofScan help me choose between devices?", answer: "Buyer Chat compares the signed reports shared with your account and can include your saved listings. It cites the sources behind its recommendations and calls out missing measurements." },
];

export function MarketingLanding() {
  return <div className="pitch">
    <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(siteSchema).replace(/</g, "\\u003c") }} />
    <a className="skip-link" href="#main">Skip to content</a>
    <header className="pitch-header">
      <div className="pitch-width pitch-header-inner">
        <Brand />
        <nav className="pitch-nav" aria-label="Product"><a href="#product">Product</a><a href="#how-it-works">How it works</a><a href="#download">Downloads</a></nav>
        <Link className="pitch-button pitch-button-outline" href="/workspace">Open workspace</Link>
      </div>
    </header>
    <main id="main" tabIndex={-1}>
      <section className="pitch-hero" aria-labelledby="pitch-title">
        <div className="pitch-hero-art"><Image src="/marketing/proofscan-hero.webp" alt="" fill preload unoptimized sizes="(max-width: 700px) 100vw, 72vw" /></div>
        <div className="pitch-width pitch-hero-content">
          <h1 id="pitch-title">Used tech.<br /><em>Real evidence.</em></h1>
          <p>ProofScan puts hardware readings and exterior photos in a signed report, so you can check a used device before you pay.</p>
          <div className="pitch-actions">
            <a className="pitch-button pitch-button-accent" href="#demo">Explore the demo</a>
            <a className="pitch-button pitch-button-outline" href="#download">Get ProofScan</a>
          </div>
        </div>
      </section>
      <section id="product" className="pitch-section pitch-proof" aria-labelledby="proof-title">
        <div className="pitch-width pitch-proof-grid">
          <div className="pitch-section-copy">
            <h2 id="proof-title">See what the listing leaves out.</h2>
            <p>Put the seller’s claims next to the readings and photos collected from the device. Spot a smaller drive, check what changed at pickup, or compare condition when equipment comes back.</p>
            <p>When you’re choosing between devices, <Link href="/advisor">Buyer Chat</Link> compares the signed reports shared with you.</p>
          </div>
          <div id="demo"><EvidenceDemo /></div>
        </div>
      </section>
      <section id="how-it-works" className="pitch-section pitch-process" aria-labelledby="process-title">
        <div className="pitch-width">
          <div className="pitch-section-copy"><h2 id="process-title">From listing to pickup.</h2><p>One record carries the evidence through the sale.</p></div>
          <ol className="pitch-steps">{steps.map(({ title, detail, Icon }) => <li key={title}>
            <span className="pitch-step-icon"><Icon size={23} aria-hidden /></span><h3>{title}</h3><p>{detail}</p>
          </li>)}</ol>
        </div>
      </section>
      <section id="download" className="pitch-section pitch-download" aria-labelledby="download-title">
        <div className="pitch-width pitch-download-grid">
          <div className="pitch-section-copy"><h2 id="download-title">Get ProofScan.</h2><p>Start a verification, review a report, or check a handoff in your browser. Use a collector when you need readings from the device itself.</p>
            <div className="pitch-actions"><Link className="pitch-button pitch-button-dark" href="/workspace">Open web workspace</Link></div>
          </div>
          <ul className="pitch-platforms">{clients.map(({ name, note, Icon, href, action, localFile }) => <li key={name}>
            <span className="pitch-platform-icon"><Icon size={22} aria-hidden /></span>
            <div><h3>{name}</h3><p>{note}</p></div>
            <a className="pitch-platform-link" href={href} download={localFile || undefined}>{localFile && <Download size={16} aria-hidden />}{action}</a>
          </li>)}</ul>
        </div>
      </section>
      <section id="faq" className="pitch-section pitch-faq" aria-labelledby="faq-title">
        <div className="pitch-width pitch-faq-grid">
          <div className="pitch-section-copy"><h2 id="faq-title">Before you get started.</h2><p>How the evidence, sharing, and pickup checks work.</p></div>
          <div className="pitch-questions">{questions.map(({ question, answer }) => <details key={question}>
            <summary>{question}</summary><p>{answer}</p>
          </details>)}</div>
        </div>
      </section>
    </main>
    <footer className="pitch-footer" aria-label="ProofScan information">
      <div className="pitch-width pitch-footer-inner">
        <Brand />
        <nav aria-label="Product information"><Link href="/about">About</Link><Link href="/help">Help</Link><Link href="/privacy">Privacy</Link><Link href="/verify">Check a report</Link></nav>
        <span>Web version {version}</span>
      </div>
    </footer>
  </div>;
}

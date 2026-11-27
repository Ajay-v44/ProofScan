import type { Metadata } from "next";
import { Workspace } from "../../components/workspace";

export const metadata: Metadata = { title: "Workspace", robots: { index: false, follow: false } };

export default async function Page({ searchParams }: { searchParams: Promise<{ view?: string; action?: string }> }) {
  const { view, action } = await searchParams;
  const initialSection = view === "verifications" ? "Verifications" : view === "activity" ? "Activity" : "Home";
  const initialOverlay = action === "search" || action === "seller" || action === "new" ? action : null;
  return <Workspace key={initialSection + ":" + initialOverlay} initialSection={initialSection} initialOverlay={initialOverlay} />;
}

import { Workspace } from "../components/workspace";

export default async function Page({ searchParams }: { searchParams: Promise<{ view?: string; action?: string }> }) {
  const { view, action } = await searchParams;
  const initialSection = view === "verifications" ? "Verifications" : view === "activity" ? "Activity" : "Home";
  const initialOverlay = action === "search" ? "search" : action === "seller" ? "seller" : null;
  return <Workspace key={initialSection + ":" + initialOverlay} initialSection={initialSection} initialOverlay={initialOverlay} />;
}

import { CompanionCapture } from "../../../components/companion-capture";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  return <CompanionCapture id={(await params).id} />;
}

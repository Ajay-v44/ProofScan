import { HandoffDetail } from "../../../components/handoffs";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  return <HandoffDetail id={(await params).id} />;
}

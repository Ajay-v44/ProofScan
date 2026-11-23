import { AcceptHandoff } from "../../../components/handoffs";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  return <AcceptHandoff id={(await params).id} />;
}

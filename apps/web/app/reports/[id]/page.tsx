import { BuyerReport } from "../../../components/report-pages";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  return <BuyerReport id={(await params).id} />;
}

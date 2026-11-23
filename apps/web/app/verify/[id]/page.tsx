import { VerifyReport } from "../../../components/report-pages";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  return <VerifyReport id={(await params).id} />;
}

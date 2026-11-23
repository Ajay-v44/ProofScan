import { Seller } from "../../../components/seller";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  return <Seller id={(await params).id} />;
}

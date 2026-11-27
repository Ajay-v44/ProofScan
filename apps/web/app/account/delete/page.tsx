import type { Metadata } from "next";
import { DeleteAccount } from "../../../components/delete-account";

export const metadata: Metadata = { title: "Delete your ProofScan account" };

export default function DeleteAccountPage() {
  return <DeleteAccount />;
}

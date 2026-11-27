import type { Metadata } from "next";
import { AccountPage } from "../../components/account-pages";

export const metadata: Metadata = { title: "Set a new password", robots: { index: false, follow: false } };

export default function Page() {
  return <AccountPage mode="reset-password" />;
}

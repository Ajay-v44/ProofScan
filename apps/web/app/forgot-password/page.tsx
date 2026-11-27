import type { Metadata } from "next";
import { AccountPage } from "../../components/account-pages";

export const metadata: Metadata = { title: "Password recovery", robots: { index: false, follow: false } };

export default function Page() {
  return <AccountPage mode="forgot-password" />;
}

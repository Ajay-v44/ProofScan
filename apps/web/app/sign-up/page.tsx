import type { Metadata } from "next";
import { AccountPage } from "../../components/account-pages";
import { accountDestination } from "../../components/account-navigation";

export const metadata: Metadata = { title: "Create an account", robots: { index: false, follow: false } };

export default async function Page({ searchParams }: { searchParams: Promise<{ next?: string }> }) {
  const { next } = await searchParams;
  return <AccountPage mode="sign-up" next={accountDestination(next)} />;
}

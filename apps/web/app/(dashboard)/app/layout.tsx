import type { ReactNode } from "react";
import { AppShell } from "../../../components/app-shell";
import { requireSession } from "../../../lib/server-auth";

export default async function HouseholdLayout({
  children
}: Readonly<{
  children: ReactNode;
}>) {
  const session = await requireSession();

  return <AppShell session={session}>{children}</AppShell>;
}

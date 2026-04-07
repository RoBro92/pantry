import type { ReactNode } from "react";
import { AppShell } from "../../components/app-shell";
import { getReleaseStatus, requireSession } from "../../lib/server-auth";

export default async function DashboardLayout({
  children
}: Readonly<{
  children: ReactNode;
}>) {
  const session = await requireSession();
  const releaseStatus =
    session.user.platform_role === "platform_admin" ? await getReleaseStatus() : null;
  return (
    <AppShell session={session} releaseStatus={releaseStatus}>
      {children}
    </AppShell>
  );
}

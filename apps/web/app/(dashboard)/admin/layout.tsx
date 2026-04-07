import type { ReactNode } from "react";
import { AdminSectionNav } from "../../../components/admin-section-nav";
import { requirePlatformAdminSession } from "../../../lib/server-auth";

export default async function AdminLayout({
  children
}: Readonly<{
  children: ReactNode;
}>) {
  await requirePlatformAdminSession();

  return (
    <div className="stack">
      <section className="panel">
        <p className="eyebrow">Platform Admin</p>
        <h1>Installation Console</h1>
        <p>
          This dashboard provides administrative tools for managing your Pantry install.
        </p>
        <AdminSectionNav />
      </section>
      {children}
    </div>
  );
}

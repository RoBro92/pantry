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
          Installation-level controls stay separate from household workflows. Diagnostics and
          configuration surfaces only show data the running application can actually measure.
        </p>
        <AdminSectionNav />
      </section>
      {children}
    </div>
  );
}

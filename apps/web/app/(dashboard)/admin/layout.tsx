import type { ReactNode } from "react";
import { AdminUpdateBanner } from "../../../components/admin-update-banner";
import { AdminSectionNav } from "../../../components/admin-section-nav";
import { getReleaseStatus, requirePlatformAdminSession } from "../../../lib/server-auth";

export default async function AdminLayout({
  children
}: Readonly<{
  children: ReactNode;
}>) {
  await requirePlatformAdminSession();
  const releaseStatus = await getReleaseStatus();

  return (
    <div className="stack">
      <section className="panel">
        <p className="eyebrow">Admin Dashboard</p>
        <h1>Installation console</h1>
        <p>
          This dashboard provides administrative tools for managing your Pantro install.
        </p>
        <AdminSectionNav />
      </section>
      <AdminUpdateBanner releaseStatus={releaseStatus} />
      {children}
    </div>
  );
}

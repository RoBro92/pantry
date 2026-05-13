import Link from "next/link";
import type { ReactNode } from "react";
import { AdminReleaseNotesDialog } from "../../../components/admin-release-notes-dialog";
import { AdminUpdateBanner } from "../../../components/admin-update-banner";
import { AdminSectionNav } from "../../../components/admin-section-nav";
import { LogoutButtonInner } from "../../../components/logout-button";
import { getReleaseStatus, requirePlatformAdminSession } from "../../../lib/server-auth";

export default async function AdminLayout({
  children
}: Readonly<{
  children: ReactNode;
}>) {
  const session = await requirePlatformAdminSession();
  const releaseStatus = await getReleaseStatus();
  const displayName = session.user.display_name ?? session.user.email;

  return (
    <main className="page-shell dashboard-page-shell">
      <AdminReleaseNotesDialog initialReleaseStatus={releaseStatus} />

      <div className="mobile-shell-header admin-mobile-shell-header">
        <div className="mobile-shell-topbar">
          <div className="stack compact-stack">
            <p className="eyebrow">Installation</p>
            <h1 className="shell-title mobile-shell-title">Admin console</h1>
            <p className="sidebar-copy">{displayName}</p>
          </div>
          <LogoutButtonInner className="ghost-button compact-button" />
        </div>
        <nav className="mobile-shell-utility-links" aria-label="Installation quick links">
          <Link href="/app" className="shell-nav-link">
            Household dashboard
          </Link>
          <Link href="/app/settings" className="shell-nav-link">
            Account settings
          </Link>
          <Link href="/admin" className="shell-nav-link">
            Admin home
          </Link>
        </nav>
      </div>

      <div className="shell-grid">
        <aside className="sidebar panel">
          <p className="eyebrow">Pantro</p>
          <h1 className="shell-title">Installation</h1>
          <p className="sidebar-copy">{displayName}</p>
          <nav className="nav-list" aria-label="Installation navigation">
            <Link href="/app" className="shell-nav-link">
              Household dashboard
            </Link>
            <Link href="/app/settings" className="shell-nav-link">
              Account settings
            </Link>
            <div className="nav-group">
              <span className="nav-group-title">Operator tools</span>
              <Link href="/admin" className="shell-nav-link">
                Installation console
              </Link>
            </div>
          </nav>
          <LogoutButtonInner />
        </aside>

        <section className="shell-content stack">
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
        </section>
      </div>
    </main>
  );
}

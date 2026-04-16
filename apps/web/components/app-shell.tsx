import Link from "next/link";
import type { ReactNode } from "react";
import type { ReleaseCheckResponse, SessionResponse } from "../lib/api-types";
import { appConfig } from "../lib/app-config";
import { AdminReleaseNotesDialog } from "./admin-release-notes-dialog";
import { LogoutButton } from "./logout-button";

type AppShellProps = {
  session: SessionResponse;
  releaseStatus?: ReleaseCheckResponse | null;
  children: ReactNode;
};

export function AppShell({ session, releaseStatus, children }: AppShellProps) {
  return (
    <main className="page-shell dashboard-page-shell">
      {releaseStatus ? <AdminReleaseNotesDialog initialReleaseStatus={releaseStatus} /> : null}
      <div className="shell-grid">
        <aside className="sidebar panel">
          <p className="eyebrow">Pantro {appConfig.version}</p>
          <h1 className="shell-title">Navigation</h1>
          <p className="sidebar-copy">
            {session.memberships.length} household
            {session.memberships.length === 1 ? "" : "s"} visible
          </p>
          <nav className="nav-list">
            <Link href="/app">Dashboard</Link>
            <Link href="/app/settings">Settings</Link>
            {session.memberships.map((membership) => (
              <div key={membership.external_id} className="nav-group">
                <span className="nav-group-title">{membership.household_name}</span>
                <Link href={`/app/households/${membership.household_external_id}`}>Pantro</Link>
                <Link href={`/app/households/${membership.household_external_id}/shopping-list`}>
                  Shopping List
                </Link>
                <Link href={`/app/households/${membership.household_external_id}/shopping-list/history`}>
                  Shopping History
                </Link>
                <Link href={`/app/households/${membership.household_external_id}/imports`}>
                  Imports
                </Link>
                <Link href={`/app/households/${membership.household_external_id}/recipes`}>
                  Recipes
                </Link>
                <Link href={`/app/households/${membership.household_external_id}/ai`}>
                  Meal Suggestions
                </Link>
              </div>
            ))}
            {session.user.platform_role === "platform_admin" ? (
              <div className="nav-group">
                <Link href="/admin" className="sidebar-admin-link">
                  Admin Dashboard
                </Link>
              </div>
            ) : null}
          </nav>
          {session.memberships.length === 0 ? (
            <p className="sidebar-copy">
              Households appear here after a platform admin assigns memberships.
            </p>
          ) : null}
          <LogoutButton />
        </aside>
        <section className="shell-content">{children}</section>
      </div>
    </main>
  );
}

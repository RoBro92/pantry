import Link from "next/link";
import type { ReactNode } from "react";
import type { SessionResponse } from "../lib/api-types";
import { LogoutButton } from "./logout-button";

type AppShellProps = {
  session: SessionResponse;
  children: ReactNode;
};

export function AppShell({ session, children }: AppShellProps) {
  return (
    <main className="page-shell">
      <div className="shell-grid">
        <aside className="sidebar panel">
          <p className="eyebrow">Pantry</p>
          <h1 className="shell-title">Household Shell</h1>
          <p className="sidebar-copy">
            Logged in as {session.user.display_name ?? session.user.email}
          </p>
          <nav className="nav-list">
            <Link href="/app">Dashboard</Link>
            {session.memberships.map((membership) => (
              <div key={membership.external_id} className="nav-group">
                <span className="nav-group-title">{membership.household_name}</span>
                <Link href={`/app/households/${membership.household_external_id}`}>Pantry</Link>
                <Link href={`/app/households/${membership.household_external_id}/imports`}>
                  Imports
                </Link>
                <Link href={`/app/households/${membership.household_external_id}/recipes`}>
                  Recipes
                </Link>
                <Link href={`/app/households/${membership.household_external_id}/ai`}>
                  AI Suggestions
                </Link>
              </div>
            ))}
            {session.user.platform_role === "platform_admin" ? (
              <div className="nav-group">
                <span className="nav-group-title">Platform Admin</span>
                <Link href="/admin">Overview</Link>
                <Link href="/admin/users">Users</Link>
                <Link href="/admin/households">Households</Link>
                <Link href="/admin/ai">AI</Link>
                <Link href="/admin/smtp">SMTP</Link>
                <Link href="/admin/diagnostics">Diagnostics</Link>
                <Link href="/admin/settings">Settings</Link>
              </div>
            ) : null}
          </nav>
          <LogoutButton />
        </aside>
        <section className="shell-content">{children}</section>
      </div>
    </main>
  );
}

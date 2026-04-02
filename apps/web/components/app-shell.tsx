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
          <h1 className="shell-title">Admin Shell</h1>
          <p className="sidebar-copy">
            Logged in as {session.user.display_name ?? session.user.email}
          </p>
          <nav className="nav-list">
            <Link href="/app">Session</Link>
            {session.user.platform_role === "platform_admin" ? (
              <>
                <Link href="/admin">Overview</Link>
                <Link href="/admin/users">Users</Link>
                <Link href="/admin/households">Households</Link>
              </>
            ) : null}
          </nav>
          <LogoutButton />
        </aside>
        <section className="shell-content">{children}</section>
      </div>
    </main>
  );
}


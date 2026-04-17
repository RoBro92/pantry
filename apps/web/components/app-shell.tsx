"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import type {
  ReleaseCheckResponse,
  SessionMembership,
  SessionResponse,
} from "../lib/api-types";
import { appConfig } from "../lib/app-config";
import { AdminReleaseNotesDialog } from "./admin-release-notes-dialog";
import { LogoutButton } from "./logout-button";

type AppShellProps = {
  session: SessionResponse;
  releaseStatus?: ReleaseCheckResponse | null;
  children: ReactNode;
};

type NavItem = {
  href: string;
  label: string;
  matchPrefix?: string;
};

function isActiveNav(pathname: string, item: NavItem) {
  if (pathname === item.href) {
    return true;
  }
  return item.matchPrefix ? pathname.startsWith(item.matchPrefix) : false;
}

function AppShellNavLink({ item, pathname }: { item: NavItem; pathname: string }) {
  const isActive = isActiveNav(pathname, item);

  return (
    <Link
      href={item.href}
      className={`shell-nav-link${isActive ? " shell-nav-link-active" : ""}`}
      aria-current={isActive ? "page" : undefined}
    >
      {item.label}
    </Link>
  );
}

function getHouseholdNavItems(membership: SessionMembership): NavItem[] {
  const basePath = `/app/households/${membership.household_external_id}`;

  return [
    {
      href: basePath,
      label: "Inventory",
      matchPrefix: `${basePath}/`,
    },
    {
      href: `${basePath}/shopping-list`,
      label: "Shopping List",
      matchPrefix: `${basePath}/shopping-list`,
    },
    {
      href: `${basePath}/recipes`,
      label: "Recipes",
      matchPrefix: `${basePath}/recipes`,
    },
    {
      href: `${basePath}/ai`,
      label: "Meal Suggestions",
      matchPrefix: `${basePath}/ai`,
    },
    {
      href: `${basePath}/imports`,
      label: "Imports",
      matchPrefix: `${basePath}/imports`,
    },
  ];
}

function getCurrentMembership(pathname: string, memberships: SessionMembership[]) {
  const match = pathname.match(/^\/app\/households\/([^/]+)/);
  const currentHouseholdExternalId = match?.[1] ?? null;
  return (
    memberships.find((membership) => membership.household_external_id === currentHouseholdExternalId) ??
    memberships[0] ??
    null
  );
}

export function AppShell({ session, releaseStatus, children }: AppShellProps) {
  const pathname = usePathname() ?? "/app";
  const currentMembership = getCurrentMembership(pathname, session.memberships);
  const householdNavItems = currentMembership ? getHouseholdNavItems(currentMembership) : [];
  const mobileBottomNavItems = currentMembership
    ? householdNavItems.slice(0, 4)
    : [
        { href: "/app", label: "Dashboard" },
        { href: "/app/settings", label: "Settings", matchPrefix: "/app/settings" },
      ];

  return (
    <main className="page-shell dashboard-page-shell">
      {releaseStatus ? <AdminReleaseNotesDialog initialReleaseStatus={releaseStatus} /> : null}

      <div className="mobile-shell-header panel">
        <div className="mobile-shell-summary">
          <div className="stack compact-stack">
            <p className="eyebrow">Pantro {appConfig.version}</p>
            <h1 className="shell-title">
              {currentMembership ? currentMembership.household_name : "Households"}
            </h1>
            <p className="sidebar-copy">
              {currentMembership
                ? "Mobile household shortcuts keep pantry, shopping, and recipes within thumb reach."
                : session.memberships.length > 0
                  ? `${session.memberships.length} household${session.memberships.length === 1 ? "" : "s"} available.`
                  : "Households appear here after a platform admin assigns memberships."}
            </p>
          </div>

          <div className="mobile-shell-utility-links">
            <AppShellNavLink item={{ href: "/app", label: "Dashboard" }} pathname={pathname} />
            <AppShellNavLink
              item={{ href: "/app/settings", label: "Settings", matchPrefix: "/app/settings" }}
              pathname={pathname}
            />
            {session.user.platform_role === "platform_admin" ? (
              <AppShellNavLink
                item={{ href: "/admin", label: "Admin", matchPrefix: "/admin" }}
                pathname={pathname}
              />
            ) : null}
          </div>
        </div>

        {session.memberships.length > 0 ? (
          <div className="mobile-household-switcher">
            {session.memberships.map((membership) => {
              const membershipHref = `/app/households/${membership.household_external_id}`;
              const isActive = pathname.startsWith(membershipHref);

              return (
                <Link
                  key={membership.external_id}
                  href={membershipHref}
                  className={`mobile-household-pill${isActive ? " mobile-household-pill-active" : ""}`}
                  aria-current={isActive ? "page" : undefined}
                >
                  {membership.household_name}
                </Link>
              );
            })}
          </div>
        ) : null}

        {currentMembership ? (
          <nav className="mobile-household-nav" aria-label="Current household navigation">
            {householdNavItems.map((item) => (
              <AppShellNavLink key={item.href} item={item} pathname={pathname} />
            ))}
          </nav>
        ) : null}
      </div>

      <div className="shell-grid">
        <aside className="sidebar panel">
          <p className="eyebrow">Pantro {appConfig.version}</p>
          <h1 className="shell-title">Navigation</h1>
          <p className="sidebar-copy">
            {session.memberships.length} household
            {session.memberships.length === 1 ? "" : "s"} visible
          </p>
          <nav className="nav-list">
            <AppShellNavLink item={{ href: "/app", label: "Dashboard" }} pathname={pathname} />
            <AppShellNavLink
              item={{ href: "/app/settings", label: "Settings", matchPrefix: "/app/settings" }}
              pathname={pathname}
            />
            {session.memberships.map((membership) => (
              <div key={membership.external_id} className="nav-group">
                <span className="nav-group-title">{membership.household_name}</span>
                {getHouseholdNavItems(membership).map((item) => (
                  <AppShellNavLink key={item.href} item={item} pathname={pathname} />
                ))}
              </div>
            ))}
            {session.user.platform_role === "platform_admin" ? (
              <div className="nav-group">
                <Link href="/admin" className="shell-nav-link sidebar-admin-link">
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

      {mobileBottomNavItems.length > 0 ? (
        <nav className="mobile-bottom-nav" aria-label="Household quick navigation">
          {mobileBottomNavItems.map((item) => {
            const isActive = isActiveNav(pathname, item);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`mobile-bottom-nav-link${isActive ? " mobile-bottom-nav-link-active" : ""}`}
                aria-current={isActive ? "page" : undefined}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      ) : null}
    </main>
  );
}

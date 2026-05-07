"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import type {
  ReleaseCheckResponse,
  SessionMembership,
  SessionResponse,
} from "../lib/api-types";
import { AdminReleaseNotesDialog } from "./admin-release-notes-dialog";
import { LogoutButtonInner } from "./logout-button";

type AppShellProps = {
  session: SessionResponse;
  releaseStatus?: ReleaseCheckResponse | null;
  children: ReactNode;
};

type NavItem = {
  href: string;
  label: string;
  mobileLabel?: string;
  matchPrefix?: string;
  isActive?: (pathname: string) => boolean;
};

function isActiveNav(pathname: string, item: NavItem) {
  if (item.isActive) {
    return item.isActive(pathname);
  }
  if (pathname === item.href) {
    return true;
  }
  return item.matchPrefix ? pathname.startsWith(item.matchPrefix) : false;
}

function AppShellNavLink({
  item,
  pathname,
  onClick,
}: {
  item: NavItem;
  pathname: string;
  onClick?: () => void;
}) {
  const isActive = isActiveNav(pathname, item);

  return (
    <Link
      href={item.href}
      className={`shell-nav-link${isActive ? " shell-nav-link-active" : ""}`}
      aria-current={isActive ? "page" : undefined}
      onClick={onClick}
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
      mobileLabel: "Stock",
      isActive: (pathname) => pathname === basePath,
    },
    {
      href: `${basePath}/shopping-list`,
      label: "Shopping List",
      mobileLabel: "Shop",
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
      mobileLabel: "Meals",
      matchPrefix: `${basePath}/ai`,
    },
    {
      href: `${basePath}/imports`,
      label: "Imports",
      mobileLabel: "Imports",
      matchPrefix: `${basePath}/imports`,
    },
  ];
}

function getCurrentMembership(pathname: string, memberships: SessionMembership[]) {
  const match = pathname.match(/^\/app\/households\/([^/]+)/);
  if (!match) {
    return null;
  }

  const currentHouseholdExternalId = match[1];
  return memberships.find((membership) => membership.household_external_id === currentHouseholdExternalId) ?? null;
}

export function AppShell({ session, releaseStatus, children }: AppShellProps) {
  const pathname = usePathname() ?? "/app";
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const currentMembership = getCurrentMembership(pathname, session.memberships);
  const householdNavItems = currentMembership ? getHouseholdNavItems(currentMembership) : [];
  const mobileBottomNavItems = currentMembership ? householdNavItems.slice(0, 4) : [];
  const mobileMenuHouseholdItems = currentMembership ? householdNavItems.slice(4) : [];
  const mobileUtilityNavItems: NavItem[] = [
    { href: "/app", label: "Dashboard" },
    { href: "/app/settings", label: "Settings", matchPrefix: "/app/settings" },
  ];
  if (session.user.platform_role === "platform_admin") {
    mobileUtilityNavItems.push({ href: "/admin", label: "Admin", matchPrefix: "/admin" });
  }

  const mobileShellTitle = currentMembership
    ? currentMembership.household_name
    : pathname.startsWith("/app/settings")
      ? "Settings"
      : "Dashboard";

  useEffect(() => {
    setIsMobileMenuOpen(false);
  }, [pathname]);

  return (
    <main className="page-shell dashboard-page-shell">
      {releaseStatus ? <AdminReleaseNotesDialog initialReleaseStatus={releaseStatus} /> : null}

      <div className="mobile-shell-header">
        <div className="mobile-shell-topbar">
          <div className="stack compact-stack">
            <p className="eyebrow">{currentMembership ? "Household" : "Pantro"}</p>
            <h1 className="shell-title mobile-shell-title">{mobileShellTitle}</h1>
            {!currentMembership ? (
              <p className="sidebar-copy">
                {session.memberships.length > 0
                  ? `${session.memberships.length} household${session.memberships.length === 1 ? "" : "s"} available.`
                  : "Households appear here after a platform admin assigns memberships."}
              </p>
            ) : null}
          </div>

          <div className="mobile-account-menu">
            <button
              type="button"
              className="ghost-button compact-button mobile-account-menu-trigger"
              aria-expanded={isMobileMenuOpen}
              aria-controls="mobile-account-menu-panel"
              onClick={() => setIsMobileMenuOpen((current) => !current)}
            >
              Menu
            </button>
            {isMobileMenuOpen ? (
              <>
                <button
                  type="button"
                  className="mobile-account-menu-scrim"
                  aria-label="Close menu"
                  onClick={() => setIsMobileMenuOpen(false)}
                />
                <div className="mobile-account-menu-panel" id="mobile-account-menu-panel">
                  {mobileMenuHouseholdItems.length > 0 ? (
                    <div className="mobile-account-menu-links">
                      {mobileMenuHouseholdItems.map((item) => (
                        <AppShellNavLink
                          key={item.href}
                          item={item}
                          pathname={pathname}
                          onClick={() => setIsMobileMenuOpen(false)}
                        />
                      ))}
                    </div>
                  ) : null}
                  <div className="mobile-account-menu-links">
                    {mobileUtilityNavItems.map((item) => (
                      <AppShellNavLink
                        key={item.href}
                        item={item}
                        pathname={pathname}
                        onClick={() => setIsMobileMenuOpen(false)}
                      />
                    ))}
                  </div>
                  <LogoutButtonInner
                    className="ghost-button compact-button mobile-account-menu-logout"
                  />
                </div>
              </>
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
      </div>

      <div className="shell-grid">
        <aside className="sidebar panel">
          <p className="eyebrow">Pantro</p>
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
                <AppShellNavLink
                  item={{ href: "/admin", label: "Admin Dashboard", matchPrefix: "/admin" }}
                  pathname={pathname}
                />
              </div>
            ) : null}
          </nav>
          {session.memberships.length === 0 ? (
            <p className="sidebar-copy">
              Households appear here after a platform admin assigns memberships.
            </p>
          ) : null}
          <LogoutButtonInner />
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
                aria-label={item.label}
                aria-current={isActive ? "page" : undefined}
              >
                <span className="mobile-bottom-nav-link-text">
                  {item.mobileLabel ?? item.label}
                </span>
              </Link>
            );
          })}
        </nav>
      ) : null}
    </main>
  );
}

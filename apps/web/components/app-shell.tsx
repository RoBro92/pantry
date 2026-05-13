"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import type { SessionMembership, SessionResponse } from "../lib/api-types";
import { LogoutButtonInner } from "./logout-button";

type AppShellProps = {
  session: SessionResponse;
  children: ReactNode;
};

type NavItem = {
  id?: "pantry" | "add" | "shopping" | "recipes" | "more";
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
      id: "pantry",
      href: basePath,
      label: "Pantry",
      isActive: (pathname) => pathname === basePath,
    },
    {
      id: "shopping",
      href: `${basePath}/shopping-list`,
      label: "Shopping",
      matchPrefix: `${basePath}/shopping-list`,
    },
    {
      id: "recipes",
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

export function AppShell({ session, children }: AppShellProps) {
  const pathname = usePathname() ?? "/app";
  const searchParams = useSearchParams();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const currentMembership = getCurrentMembership(pathname, session.memberships);
  const householdNavItems = currentMembership ? getHouseholdNavItems(currentMembership) : [];
  const currentHouseholdBasePath = currentMembership
    ? `/app/households/${currentMembership.household_external_id}`
    : null;
  const mobileBottomNavItems: NavItem[] = currentHouseholdBasePath
    ? [
        {
          id: "pantry",
          href: currentHouseholdBasePath,
          label: "Pantry",
          isActive: (currentPathname) =>
            currentPathname === currentHouseholdBasePath && !searchParams.get("add"),
        },
        {
          id: "add",
          href: `${currentHouseholdBasePath}?add=scan`,
          label: "Add / Scan",
          mobileLabel: "Add",
          isActive: (currentPathname) =>
            currentPathname === currentHouseholdBasePath && Boolean(searchParams.get("add")),
        },
        {
          id: "shopping",
          href: `${currentHouseholdBasePath}/shopping-list`,
          label: "Shopping",
          mobileLabel: "Shop",
          matchPrefix: `${currentHouseholdBasePath}/shopping-list`,
        },
        {
          id: "recipes",
          href: `${currentHouseholdBasePath}/recipes`,
          label: "Recipes",
          matchPrefix: `${currentHouseholdBasePath}/recipes`,
        },
      ]
    : [];
  const mobileMenuHouseholdItems: NavItem[] = currentHouseholdBasePath
    ? [
        { href: `${currentHouseholdBasePath}?add=manual`, label: "Add manually" },
        { href: `${currentHouseholdBasePath}?add=quick`, label: "Bulk scan" },
        ...householdNavItems.filter((item) => !["pantry", "shopping", "recipes"].includes(item.id ?? "")),
      ]
    : [];
  const mobileUtilityNavItems: NavItem[] = [
    { href: "/app", label: "Dashboard" },
    { href: "/app/settings", label: "Settings", matchPrefix: "/app/settings" },
  ];

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
              Account
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
          <button
            type="button"
            className={`mobile-bottom-nav-link mobile-bottom-nav-more${isMobileMenuOpen ? " mobile-bottom-nav-link-active" : ""}`}
            aria-label="More household options"
            aria-expanded={isMobileMenuOpen}
            aria-controls="mobile-account-menu-panel"
            onClick={() => setIsMobileMenuOpen((current) => !current)}
          >
            <span className="mobile-bottom-nav-link-text">More</span>
          </button>
        </nav>
      ) : null}
    </main>
  );
}

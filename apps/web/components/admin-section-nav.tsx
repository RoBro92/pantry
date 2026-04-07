"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const adminLinks = [
  { href: "/admin", label: "Dashboard" },
  { href: "/admin/users", label: "Users" },
  { href: "/admin/households", label: "Households" },
  { href: "/admin/ai", label: "AI" },
  { href: "/admin/smtp", label: "SMTP" },
  { href: "/admin/diagnostics", label: "Diagnostics" },
  { href: "/admin/settings", label: "Settings" }
];

export function AdminSectionNav() {
  const pathname = usePathname();

  return (
    <nav className="admin-nav" aria-label="Platform admin sections">
      {adminLinks.map((link) => {
        const isActive =
          pathname === link.href || (link.href !== "/admin" && pathname.startsWith(`${link.href}/`));

        return (
          <Link
            key={link.href}
            href={link.href}
            className={isActive ? "admin-nav-link admin-nav-link-active" : "admin-nav-link"}
          >
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}

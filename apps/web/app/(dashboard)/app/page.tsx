import Link from "next/link";
import { getHouseholdRoleLabel } from "../../../lib/role-labels";
import { requireSession } from "../../../lib/server-auth";

export default async function SessionPage() {
  const session = await requireSession();
  const displayName = session.user.display_name ?? session.user.email;

  return (
    <div className="stack">
      <section className="panel dashboard-welcome-panel">
        <p className="eyebrow">Dashboard</p>
        <h1>Welcome back {displayName}</h1>
        <p className="helper-text">
          {session.memberships.length} household{session.memberships.length === 1 ? "" : "s"} ready.
        </p>
      </section>

      <section className="panel">
        <p className="eyebrow">Pantro Households</p>
        {session.memberships.length === 0 ? (
          session.user.platform_role === "platform_admin" ? (
            <div className="stack">
              <p>
                No active household memberships yet. Create a household and assign at least one
                membership from the installation console to start using pantry.
              </p>
              <div className="page-actions">
                <Link href="/app/settings" className="secondary-link">
                  Account settings
                </Link>
                <Link href="/admin/households" className="primary-link">
                  Open household setup
                </Link>
                <Link href="/admin/users" className="secondary-link">
                  Manage users
                </Link>
              </div>
            </div>
          ) : (
            <p>
              No active household memberships yet. Ask an admin to assign this account to a
              household.
            </p>
          )
        ) : (
          <div className="household-card-grid">
            {session.memberships.map((membership) => (
              <article key={membership.external_id} className="household-card">
                <div className="stack compact-stack">
                  <strong>{membership.household_name}</strong>
                  <p>{getHouseholdRoleLabel(membership.role)}</p>
                </div>
                <div className="household-card-actions">
                  <Link
                    href={`/app/households/${membership.household_external_id}`}
                    className="primary-link compact-link"
                  >
                    Inventory
                  </Link>
                  <Link
                    href={`/app/households/${membership.household_external_id}/recipes`}
                    className="secondary-link compact-link"
                  >
                    Recipes
                  </Link>
                  <Link
                    href={`/app/households/${membership.household_external_id}/ai`}
                    className="secondary-link compact-link"
                  >
                    Meals
                  </Link>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      {session.user.platform_role === "platform_admin" ? (
      <section className="panel">
        <p className="eyebrow">Admin</p>
        <p>
          The admin dashboard provides installation-level tools for managing households, users,
          and memberships across Pantro.
        </p>
          <Link href="/admin" className="primary-link">
            Open admin dashboard
          </Link>
        </section>
      ) : null}
    </div>
  );
}

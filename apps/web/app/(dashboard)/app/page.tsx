import Link from "next/link";
import { StatusCard } from "../../../components/status-card";
import { getHouseholdRoleLabel, getPlatformRoleLabel } from "../../../lib/role-labels";
import { requireSession } from "../../../lib/server-auth";

export default async function SessionPage() {
  const session = await requireSession();

  return (
    <div className="stack">
      <section className="panel">
        <h1>Welcome back {session.user.display_name ?? session.user.email}</h1>
        <p className="helper-text">
          Logged in as {session.user.display_name ?? session.user.email}
        </p>
        <p>
          This is your Pantry dashboard, where you can access your households, view your memberships, and manage your account. Use the links below to navigate to different sections of the app and start organizing your pantry!
        </p>
      </section>

      <section className="status-grid">
        <StatusCard
          title="User"
          value={session.user.display_name ?? session.user.email}
          detail={session.user.email}
        />
        <StatusCard
          title="Platform Role"
          value={getPlatformRoleLabel(session.user.platform_role)}
          detail="Platform-wide access for this signed-in account."
        />
        <StatusCard
          title="Memberships"
          value={String(session.memberships.length)}
          detail="Household relationships are resolved server-side."
        />
      </section>

      <section className="panel">
        <p className="eyebrow">Pantry Households</p>
        {session.memberships.length === 0 ? (
          session.user.platform_role === "platform_admin" ? (
            <div className="stack">
              <p>
                No active household memberships yet. Create a household and assign at least one
                membership from the installation console to start using pantry.
              </p>
              <div className="page-actions">
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
                <div>
                  <strong>{membership.household_name}</strong>
                  <p>{getHouseholdRoleLabel(membership.role)}</p>
                </div>
                <div className="household-card-actions">
                  <Link
                    href={`/app/households/${membership.household_external_id}`}
                    className="primary-link"
                  >
                    Open Pantry
                  </Link>
                  <Link
                    href={`/app/households/${membership.household_external_id}/recipes`}
                    className="secondary-link"
                  >
                    Open recipes
                  </Link>
                  <Link
                    href={`/app/households/${membership.household_external_id}/ai`}
                    className="secondary-link"
                  >
                    Open AI
                  </Link>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      {session.user.platform_role === "platform_admin" ? (
        <section className="panel">
          <p className="eyebrow">Platform Admin</p>
          <p>
            The admin dashboard provides installation-level tools for managing households, users,
            and memberships across Pantry.
          </p>
          <Link href="/admin" className="primary-link">
            Open admin dashboard
          </Link>
        </section>
      ) : null}
    </div>
  );
}

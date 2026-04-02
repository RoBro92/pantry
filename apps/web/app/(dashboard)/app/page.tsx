import Link from "next/link";
import { StatusCard } from "../../../components/status-card";
import { requireSession } from "../../../lib/server-auth";

export default async function SessionPage() {
  const session = await requireSession();

  return (
    <div className="stack">
      <section className="panel">
        <p className="eyebrow">Authenticated Session</p>
        <h1>Welcome back</h1>
        <p>
          This shell is intentionally small. It confirms the current login,
          role, and household memberships before later household workflows are
          added.
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
          value={session.user.platform_role ?? "none"}
          detail="Platform-wide role assignment from the API session."
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
          <p>No active household memberships yet.</p>
        ) : (
          <div className="household-card-grid">
            {session.memberships.map((membership) => (
              <article key={membership.external_id} className="household-card">
                <div>
                  <strong>{membership.household_name}</strong>
                  <p>{membership.role}</p>
                </div>
                <div className="household-card-actions">
                  <Link
                    href={`/app/households/${membership.household_external_id}`}
                    className="primary-link"
                  >
                    Open pantry
                  </Link>
                  <Link
                    href={`/app/households/${membership.household_external_id}/recipes`}
                    className="secondary-link"
                  >
                    Open recipes
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
            The platform admin dashboard is available for installation-level visibility and
            direct links into household pantry views.
          </p>
          <Link href="/admin" className="primary-link">
            Open admin dashboard
          </Link>
        </section>
      ) : null}
    </div>
  );
}

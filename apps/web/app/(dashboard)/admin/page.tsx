import { AdminStatCard } from "../../../components/admin-stat-card";
import { requirePlatformAdminSession, getAdminOverview } from "../../../lib/server-auth";

export default async function AdminOverviewPage() {
  await requirePlatformAdminSession();
  const overview = await getAdminOverview();

  return (
    <div className="stack">
      <section className="panel">
        <p className="eyebrow">Platform Admin</p>
        <h1>Overview</h1>
        <p>
          This is the initial installation-level dashboard for Milestone 1. It
          stays read-oriented for now and leaves richer admin workflows for
          follow-up passes.
        </p>
      </section>

      <section className="status-grid">
        <AdminStatCard
          label="Users"
          value={overview.user_count}
          detail="All known user accounts in the installation."
        />
        <AdminStatCard
          label="Platform Admins"
          value={overview.platform_admin_count}
          detail="Users with cross-household administration rights."
        />
        <AdminStatCard
          label="Households"
          value={overview.household_count}
          detail="Household tenant records in the system."
        />
        <AdminStatCard
          label="Memberships"
          value={overview.membership_count}
          detail="User-to-household membership assignments."
        />
      </section>
    </div>
  );
}


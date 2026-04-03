import Link from "next/link";
import { AdminStatCard } from "../../../components/admin-stat-card";
import { StatusCard } from "../../../components/status-card";
import {
  getAIProviderConfig,
  getAdminOverview,
  getPublicBaseURL,
  getSMTPConfig
} from "../../../lib/server-auth";

export default async function AdminOverviewPage() {
  const [overview, aiConfig, smtpConfig, publicBaseUrl] = await Promise.all([
    getAdminOverview(),
    getAIProviderConfig(),
    getSMTPConfig(),
    getPublicBaseURL()
  ]);

  return (
    <div className="stack">
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

      <section className="status-grid">
        <StatusCard
          title="AI Provider"
          value={aiConfig.config?.provider_type ?? "none"}
          detail={
            aiConfig.config
              ? `Configured as ${aiConfig.config.provider_type} with ${aiConfig.config.health_status} health.`
              : "No instance AI provider is configured."
          }
        />
        <StatusCard
          title="SMTP"
          value={smtpConfig.configured ? "configured" : "not ready"}
          detail={
            smtpConfig.configured
              ? `SMTP is configured with ${smtpConfig.last_test_status} test status.`
              : "SMTP is not ready yet."
          }
        />
        <StatusCard
          title="Browser URL"
          value={publicBaseUrl.effective_source}
          detail={`Location QR links currently use ${publicBaseUrl.effective_value}.`}
        />
      </section>

      <section className="content-grid">
        <article className="panel">
          <p className="eyebrow">Getting Started</p>
          <h2>Make the install usable</h2>
          <p>
            Create at least one household, add users, and assign memberships before expecting
            pantry routes to show day-to-day data.
          </p>
          <div className="page-actions">
            <Link href="/admin/users" className="secondary-link">
              Create users
            </Link>
            <Link href="/admin/households" className="primary-link">
              Create households
            </Link>
            <Link href="/admin/settings" className="secondary-link">
              Set browser URL
            </Link>
          </div>
        </article>
        <article className="panel">
          <p className="eyebrow">Real Data Policy</p>
          <h2>Measured only</h2>
          <p>
            Admin diagnostics intentionally omit host CPU, memory, and disk metrics because the
            app cannot observe them directly in a portable self-hosted deployment.
          </p>
        </article>
      </section>
    </div>
  );
}

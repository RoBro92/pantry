import Link from "next/link";
import { AdminStatCard } from "../../../components/admin-stat-card";
import { StatusCard } from "../../../components/status-card";
import {
  formatAdminDateTime,
  getAIProviderLabel,
  getConfigSourceLabel,
  getReleaseStatusLabel
} from "../../../lib/admin-display";
import {
  getAIProviderConfig,
  getAdminOverview,
  getPublicBaseURL,
  getReleaseStatus,
  getSMTPConfig
} from "../../../lib/server-auth";

export default async function AdminOverviewPage() {
  const [overview, aiConfig, smtpConfig, publicBaseUrl, releaseStatus] = await Promise.all([
    getAdminOverview(),
    getAIProviderConfig(),
    getSMTPConfig(),
    getPublicBaseURL(),
    getReleaseStatus()
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
          value={getAIProviderLabel(aiConfig.config?.provider_type)}
          detail={
            aiConfig.config
              ? `${getAIProviderLabel(aiConfig.config.provider_type)} is ${aiConfig.config.health_status}.`
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
          value={getConfigSourceLabel(publicBaseUrl.effective_source)}
          detail={`Location QR links currently use ${publicBaseUrl.effective_value}.`}
        />
        <StatusCard
          title="Update Check"
          value={getReleaseStatusLabel(releaseStatus.status)}
          detail={
            releaseStatus.latest_version
              ? `Current ${releaseStatus.current_version} · latest ${releaseStatus.latest_version}`
              : releaseStatus.message ?? "Release metadata is unavailable."
          }
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
          <p className="eyebrow">Release And Updates</p>
          <h2>Operator-controlled updates</h2>
          <ul className="detail-list">
            <li>
              <strong>Current version</strong>
              <span>{releaseStatus.current_version}</span>
            </li>
            <li>
              <strong>Latest release</strong>
              <span>{releaseStatus.latest_version ?? "Unavailable"}</span>
            </li>
            <li>
              <strong>Status</strong>
              <span>{getReleaseStatusLabel(releaseStatus.status)}</span>
            </li>
            <li>
              <strong>Checked</strong>
              <span>{formatAdminDateTime(releaseStatus.checked_at)}</span>
            </li>
          </ul>
          <p>
            Pantry only checks published release metadata. Operators still choose when to pull
            images, run migrations, and restart the stack.
          </p>
          {releaseStatus.release_notes_url ? (
            <div className="page-actions">
              <a href={releaseStatus.release_notes_url} className="secondary-link">
                Release notes
              </a>
            </div>
          ) : null}
        </article>
      </section>
    </div>
  );
}

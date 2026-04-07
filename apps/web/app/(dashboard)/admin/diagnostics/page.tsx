import { StatusCard } from "../../../../components/status-card";
import {
  formatAdminDateTime,
  formatLatencyMs,
  formatSecondsAsDuration,
  formatUptime,
  getAIProviderLabel,
  getConfigSourceLabel,
  getDeploymentModeLabel,
  getReleaseStatusLabel
} from "../../../../lib/admin-display";
import { getDiagnostics } from "../../../../lib/server-auth";

export default async function AdminDiagnosticsPage() {
  const diagnostics = await getDiagnostics();
  const updateCheck = diagnostics.release_check;

  return (
    <div className="stack">
      <section className="panel">
        <p className="eyebrow">Instance Diagnostics</p>
        <h1>Runtime State</h1>
        <p>
          This page provides a snapshot of the current runtime state of your Pantry instance, including connectivity, configuration, and operational status of key components. Use this information for troubleshooting, monitoring, and ensuring your instance is healthy and up to date.
        </p>
      </section>

      <section className="status-grid">
        <StatusCard
          title="App Version"
          value={diagnostics.app.version}
          detail={`Deployment ${getDeploymentModeLabel(diagnostics.app.deployment_mode)} · uptime ${formatUptime(diagnostics.app.uptime_seconds)}`}
        />
        <StatusCard
          title="API"
          value={diagnostics.api.status}
          detail={diagnostics.api.message ?? "API route is responding."}
        />
        <StatusCard
          title="Worker"
          value={diagnostics.worker.status}
          detail={
            diagnostics.worker.message ??
            `Last heartbeat ${formatAdminDateTime(diagnostics.worker.last_seen_at)}${
              diagnostics.worker.poll_interval_seconds !== null
                ? ` · every ${formatSecondsAsDuration(diagnostics.worker.poll_interval_seconds).toLowerCase()}`
                : ""
            }`
          }
        />
        <StatusCard
          title="Redis"
          value={diagnostics.redis.status}
          detail={
            diagnostics.redis.latency_ms !== null
              ? `${formatLatencyMs(diagnostics.redis.latency_ms)} ping`
              : diagnostics.redis.message ?? "Redis unavailable."
          }
        />
        <StatusCard
          title="Database"
          value={diagnostics.database.status}
          detail={
            diagnostics.database.size_pretty
              ? `${diagnostics.database.engine} · ${diagnostics.database.size_pretty} · ${formatLatencyMs(diagnostics.database.latency_ms)}`
              : diagnostics.database.note ??
                `${diagnostics.database.engine} · ${formatLatencyMs(diagnostics.database.latency_ms)}`
          }
        />
        <StatusCard
          title="SMTP"
          value={diagnostics.smtp.last_test_status}
          detail={
            diagnostics.smtp.configured
              ? `Configured via ${getConfigSourceLabel(diagnostics.smtp.effective_source)}`
              : "Not configured yet."
          }
        />
        <StatusCard
          title="Update Check"
          value={getReleaseStatusLabel(updateCheck.status)}
          detail={
            updateCheck.latest_version
              ? `Current ${updateCheck.current_version} · latest ${updateCheck.latest_version}`
              : updateCheck.message ?? "Release metadata unavailable."
          }
        />
      </section>

      <section className="content-grid">
        <article className="panel">
          <p className="eyebrow">Entity Counts</p>
          <ul className="detail-list">
            <li>
              <strong>Households</strong>
              <span>{diagnostics.counts.households}</span>
            </li>
            <li>
              <strong>Users</strong>
              <span>{diagnostics.counts.users}</span>
            </li>
            <li>
              <strong>Products</strong>
              <span>{diagnostics.counts.products}</span>
            </li>
            <li>
              <strong>Stock lots</strong>
              <span>{diagnostics.counts.stock_lots}</span>
            </li>
            <li>
              <strong>Recipes</strong>
              <span>{diagnostics.counts.recipes}</span>
            </li>
            <li>
              <strong>Import jobs</strong>
              <span>{diagnostics.counts.import_jobs}</span>
            </li>
          </ul>
        </article>

        <article className="panel">
          <p className="eyebrow">Queue And Worker</p>
          <ul className="detail-list">
            <li>
              <strong>Queued jobs</strong>
              <span>{diagnostics.queue.queued_import_jobs}</span>
            </li>
            <li>
              <strong>Processing jobs</strong>
              <span>{diagnostics.queue.processing_import_jobs}</span>
            </li>
            <li>
              <strong>Failed jobs</strong>
              <span>{diagnostics.queue.failed_import_jobs}</span>
            </li>
            <li>
              <strong>Completed jobs</strong>
              <span>{diagnostics.queue.completed_import_jobs}</span>
            </li>
            <li>
              <strong>Confirmed jobs</strong>
              <span>{diagnostics.queue.confirmed_import_jobs}</span>
            </li>
            <li>
              <strong>Worker poll interval</strong>
              <span>
                {diagnostics.worker.poll_interval_seconds !== null
                  ? formatSecondsAsDuration(diagnostics.worker.poll_interval_seconds)
                  : "Unavailable"}
              </span>
            </li>
            <li>
              <strong>Last heartbeat</strong>
              <span>{formatAdminDateTime(diagnostics.worker.last_seen_at)}</span>
            </li>
            <li>
              <strong>Heartbeat age</strong>
              <span>{formatSecondsAsDuration(diagnostics.worker.heartbeat_age_seconds)}</span>
            </li>
          </ul>
        </article>

        <article className="panel">
          <p className="eyebrow">Configuration Summary</p>
          <ul className="detail-list">
            <li>
              <strong>Public browser URL</strong>
              <span>{diagnostics.public_base_url.effective_value}</span>
            </li>
            <li>
              <strong>Browser URL source</strong>
              <span>{getConfigSourceLabel(diagnostics.public_base_url.effective_source)}</span>
            </li>
            <li>
              <strong>AI provider</strong>
              <span>
                {diagnostics.ai_provider.configured
                  ? `${getAIProviderLabel(diagnostics.ai_provider.provider_type)} · ${diagnostics.ai_provider.health_status}`
                  : "Unconfigured"}
              </span>
            </li>
            <li>
              <strong>SMTP source</strong>
              <span>{getConfigSourceLabel(diagnostics.smtp.effective_source)}</span>
            </li>
            <li>
              <strong>SMTP test</strong>
              <span>{diagnostics.smtp.last_test_status}</span>
            </li>
            <li>
              <strong>Generated</strong>
              <span>{formatAdminDateTime(diagnostics.generated_at)}</span>
            </li>
          </ul>
        </article>

        <article className="panel">
          <p className="eyebrow">Release Update Status</p>
          <ul className="detail-list">
            <li>
              <strong>Current version</strong>
              <span>{updateCheck.current_version}</span>
            </li>
            <li>
              <strong>Latest version</strong>
              <span>{updateCheck.latest_version ?? "Unavailable"}</span>
            </li>
            <li>
              <strong>Release tag</strong>
              <span>{updateCheck.release_tag ?? "Unavailable"}</span>
            </li>
            <li>
              <strong>Repository</strong>
              <span>{updateCheck.repository ?? "Unavailable"}</span>
            </li>
            <li>
              <strong>Checked</strong>
              <span>{formatAdminDateTime(updateCheck.checked_at)}</span>
            </li>
            <li>
              <strong>Published</strong>
              <span>{formatAdminDateTime(updateCheck.published_at)}</span>
            </li>
          </ul>
          <p>{updateCheck.message ?? "Release metadata check completed."}</p>
          {updateCheck.release_notes_url ? (
            <p>
              <a href={updateCheck.release_notes_url}>Release notes</a>
            </p>
          ) : null}
        </article>
      </section>
    </div>
  );
}

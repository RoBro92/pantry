import { StatusCard } from "../../../../components/status-card";
import { getDiagnostics } from "../../../../lib/server-auth";

function formatDateTime(value: string | null) {
  if (!value) {
    return "Unavailable";
  }
  return new Date(value).toLocaleString("en-GB", {
    dateStyle: "medium",
    timeStyle: "short"
  });
}

export default async function AdminDiagnosticsPage() {
  const diagnostics = await getDiagnostics();

  return (
    <div className="stack">
      <section className="panel">
        <p className="eyebrow">Instance Diagnostics</p>
        <h1>Measured Runtime State</h1>
        <p>
          These values come from the running application process, database, Redis, and worker
          heartbeat. Unavailable fields are left unavailable instead of estimated.
        </p>
      </section>

      <section className="status-grid">
        <StatusCard
          title="App Version"
          value={diagnostics.app.version}
          detail={`Deployment mode ${diagnostics.app.deployment_mode} · uptime ${diagnostics.app.uptime_seconds}s`}
        />
        <StatusCard
          title="API"
          value={diagnostics.api.status}
          detail={diagnostics.api.message ?? "API route is responding."}
        />
        <StatusCard
          title="Worker"
          value={diagnostics.worker.status}
          detail={diagnostics.worker.message ?? `Last seen ${formatDateTime(diagnostics.worker.last_seen_at)}`}
        />
        <StatusCard
          title="Redis"
          value={diagnostics.redis.status}
          detail={
            diagnostics.redis.latency_ms !== null
              ? `${diagnostics.redis.latency_ms}ms ping`
              : diagnostics.redis.message ?? "Redis unavailable."
          }
        />
        <StatusCard
          title="Database"
          value={diagnostics.database.status}
          detail={
            diagnostics.database.size_pretty
              ? `${diagnostics.database.engine} · ${diagnostics.database.size_pretty}`
              : diagnostics.database.note ?? diagnostics.database.engine
          }
        />
        <StatusCard
          title="SMTP"
          value={diagnostics.smtp.last_test_status}
          detail={
            diagnostics.smtp.configured
              ? `Configured via ${diagnostics.smtp.effective_source}`
              : "Not configured yet."
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
              <span>{diagnostics.worker.poll_interval_seconds ?? "Unavailable"}s</span>
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
              <strong>AI provider</strong>
              <span>
                {diagnostics.ai_provider.configured
                  ? `${diagnostics.ai_provider.provider_type} · ${diagnostics.ai_provider.health_status}`
                  : "Unconfigured"}
              </span>
            </li>
            <li>
              <strong>SMTP source</strong>
              <span>{diagnostics.smtp.effective_source}</span>
            </li>
            <li>
              <strong>SMTP test</strong>
              <span>{diagnostics.smtp.last_test_status}</span>
            </li>
            <li>
              <strong>Generated</strong>
              <span>{formatDateTime(diagnostics.generated_at)}</span>
            </li>
          </ul>
        </article>
      </section>

      <section className="panel">
        <p className="eyebrow">Diagnostics Limitations</p>
        <ul className="detail-list">
          {diagnostics.limitations.map((item) => (
            <li key={item}>
              <strong>Note</strong>
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

import Link from "next/link";
import { StatusCard } from "../components/status-card";
import { appConfig } from "../lib/app-config";
import { getSetupStatus } from "../lib/server-auth";

export default async function HomePage() {
  const setupStatus = await getSetupStatus();
  return (
    <main className="page-shell">
      <section className="hero">
        <p className="eyebrow">Self-hosted foundation</p>
        <h1>{appConfig.name}</h1>
        <p className="lede">
          Pantry tracks stock lots, recipes, reviewed imports, diagnostics, QR deep links, and
          AI suggestions in a self-hosted stack that stays explicit about what is configured and
          what still needs setup.
        </p>
        <div className="hero-actions">
          <Link href={setupStatus.is_initialized ? "/login" : "/setup"} className="primary-link">
            {setupStatus.is_initialized ? "Login" : "Run setup"}
          </Link>
          <a href={`${appConfig.apiBaseUrl}/api/health`} className="secondary-link">
            API health
          </a>
        </div>
      </section>

      <section className="status-grid">
        <StatusCard
          title="Version"
          value={appConfig.version}
          detail="Derived from the canonical VERSION source used across Pantry services."
        />
        <StatusCard
          title="Setup"
          value={setupStatus.is_initialized ? "ready" : "required"}
          detail={setupStatus.recommended_next_step}
        />
        <StatusCard
          title="API"
          value="Pantry + recipes + imports"
          detail="Session auth, admin tooling, tenant-aware household access, and review-first imports."
        />
        <StatusCard
          title="Worker"
          value="Imports + recipe URLs"
          detail="Background processing for reviewed imports, recipe URL capture, and heartbeat diagnostics."
        />
      </section>

      <section className="content-grid">
        <article className="panel">
          <p className="eyebrow">Foundation</p>
          <ul>
            <li>Self-hosted first runtime</li>
            <li>Tenant-scoped pantry workflows</li>
            <li>Future hosted boundaries kept out of the UI</li>
          </ul>
        </article>
        <article className="panel">
          <p className="eyebrow">Roles</p>
          <ul>
            {appConfig.pantryRoles.map((role) => (
              <li key={role}>{role}</li>
            ))}
          </ul>
        </article>
        <article className="panel">
          <p className="eyebrow">Getting started</p>
          <ul>
            <li>Create the first platform admin.</li>
            <li>Create at least one household.</li>
            <li>Assign user memberships before regular sign-in.</li>
            <li>Set the public browser URL before printing QR links.</li>
          </ul>
        </article>
      </section>
    </main>
  );
}

import Link from "next/link";
import { StatusCard } from "../components/status-card";
import { appConfig } from "../lib/app-config";

export default function HomePage() {
  return (
    <main className="page-shell">
      <section className="hero">
        <p className="eyebrow">Self-hosted foundation</p>
        <h1>{appConfig.name}</h1>
        <p className="lede">
          Multi-household pantry management with a Next.js web app, FastAPI API,
          Python worker, PostgreSQL, Redis, and an AI abstraction layer ready
          for Ollama and OpenAI-compatible providers.
        </p>
        <div className="hero-actions">
          <Link href="/login" className="primary-link">
            Login
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
          detail="Derived from the repo VERSION file in containerized development."
        />
        <StatusCard
          title="Web"
          value="Milestone 1"
          detail="Login, authenticated shell, and platform admin pages are now scaffolded."
        />
        <StatusCard
          title="API"
          value="Auth + admin"
          detail="Session auth, admin overview endpoints, and tenant-aware household access foundations."
        />
        <StatusCard
          title="Worker"
          value="Placeholder"
          detail="Background process scaffolded with structured logs and status output."
        />
      </section>

      <section className="content-grid">
        <article className="panel">
          <p className="eyebrow">Deployment modes</p>
          <ul>
            {appConfig.deploymentModes.map((mode) => (
              <li key={mode}>{mode}</li>
            ))}
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
          <p className="eyebrow">Milestone 1 focus</p>
          <ul>
            {appConfig.domainEntities.slice(0, 4).map((entity) => (
              <li key={entity}>{entity}</li>
            ))}
          </ul>
        </article>
      </section>
    </main>
  );
}

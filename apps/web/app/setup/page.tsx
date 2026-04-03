import Link from "next/link";
import { redirect } from "next/navigation";
import { SetupBootstrapForm } from "../../components/setup-bootstrap-form";
import { getSession, getSetupStatus } from "../../lib/server-auth";

export default async function SetupPage() {
  const [session, setupStatus] = await Promise.all([getSession(), getSetupStatus()]);

  if (setupStatus.is_initialized) {
    redirect(session ? "/admin" : "/login");
  }

  return (
    <main className="page-shell">
      <section className="hero compact-hero">
        <p className="eyebrow">Self-hosted setup</p>
        <h1>Finish first-run setup</h1>
        <p className="lede">
          Create the initial platform admin, then use the installation console to create a
          household and assign memberships.
        </p>
      </section>
      <div className="auth-grid">
        <SetupBootstrapForm />
        <section className="panel">
          <p className="eyebrow">What happens next</p>
          <ol>
            <li>Create the first platform admin here.</li>
            <li>Create a household in the admin console.</li>
            <li>Assign one or more users to that household.</li>
            <li>Start using pantry, recipe, import, and QR flows.</li>
          </ol>
          <p className="section-copy">
            Prefer the CLI? You can still bootstrap with{" "}
            <code>docker compose run --rm api python -m app.cli bootstrap-platform-admin</code>.
          </p>
          <Link href="/" className="secondary-link">
            Back to home
          </Link>
        </section>
      </div>
    </main>
  );
}

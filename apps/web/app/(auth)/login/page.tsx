import { redirect } from "next/navigation";
import { LoginForm } from "../../../components/login-form";
import { getSession, getSetupStatus } from "../../../lib/server-auth";

type LoginPageProps = {
  searchParams: Promise<{
    next?: string;
  }>;
};

export default async function LoginPage({ searchParams }: LoginPageProps) {
  const [session, setupStatus] = await Promise.all([getSession(), getSetupStatus()]);
  const params = await searchParams;
  const nextPath = params.next && params.next.startsWith("/") ? params.next : "/app";
  if (session) {
    redirect(nextPath);
  }
  if (!setupStatus.is_initialized) {
    redirect("/setup");
  }

  return (
    <main className="page-shell">
      <section className="hero compact-hero">
        <p className="eyebrow">Self-hosted access</p>
        <h1>Pantry Login</h1>
        <p className="lede">
          Sign in with a Pantry account that already has household membership or platform-admin
          access.
        </p>
      </section>
      <div className="auth-grid">
        <LoginForm nextPath={nextPath} />
        <section className="panel">
          <p className="eyebrow">Before you sign in</p>
          <ul>
            <li>Use the setup flow only for the very first platform admin.</li>
            <li>Platform admins can create households and assign memberships.</li>
            <li>Users without memberships will need an admin to grant access first.</li>
          </ul>
        </section>
      </div>
    </main>
  );
}

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
      <section className="auth-stage-shell">
        <div className="auth-stage-intro">
          <p className="eyebrow">Pantry {process.env.NEXT_PUBLIC_APP_VERSION ?? ""}</p>
          <h1>Welcome back</h1>
          <p className="lede">
            Sign in to open your households, continue pantry work, or step into the installation
            console if you manage the instance.
          </p>
          <div className="setup-highlight-grid">
            <article className="setup-highlight">
              <strong>One login, clear access</strong>
              <p>Platform admins and household members land in the same polished entry flow.</p>
            </article>
            <article className="setup-highlight">
              <strong>Protected routing</strong>
              <p>Return paths are preserved when a Pantry link asks you to authenticate first.</p>
            </article>
          </div>
        </div>
        <LoginForm nextPath={nextPath} />
      </section>
    </main>
  );
}

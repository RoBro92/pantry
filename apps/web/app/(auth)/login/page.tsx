import { redirect } from "next/navigation";
import { LoginForm } from "../../../components/login-form";
import { getPasswordResetAvailability, getSession, getSetupStatus } from "../../../lib/server-auth";

type LoginPageProps = {
  searchParams: Promise<{
    next?: string;
    reset?: string;
  }>;
};

export default async function LoginPage({ searchParams }: LoginPageProps) {
  const [session, setupStatus, passwordResetAvailability] = await Promise.all([
    getSession(),
    getSetupStatus(),
    getPasswordResetAvailability()
  ]);
  const params = await searchParams;
  const nextPath = params.next && params.next.startsWith("/") ? params.next : "/app";
  const statusMessage =
    params.reset === "success" ? "Password reset complete. Sign in with your new password." : null;
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
            Sign in to view your pantry inventory, manage your shopping lists, and more.
          </p>
        </div>
        <LoginForm
          nextPath={nextPath}
          canResetPassword={passwordResetAvailability.is_available}
          statusMessage={statusMessage}
        />
      </section>
    </main>
  );
}

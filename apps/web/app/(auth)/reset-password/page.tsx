import { ResetPasswordForm } from "../../../components/reset-password-form";
import { getPasswordResetTokenStatus, getSession } from "../../../lib/server-auth";
import { redirect } from "next/navigation";

type ResetPasswordPageProps = {
  searchParams: Promise<{
    token?: string;
  }>;
};

export default async function ResetPasswordPage({ searchParams }: ResetPasswordPageProps) {
  const [session, params] = await Promise.all([getSession(), searchParams]);
  if (session) {
    redirect("/app/settings");
  }

  const token = params.token?.trim() ?? "";
  const tokenStatus = token ? await getPasswordResetTokenStatus(token) : null;

  return (
    <main className="page-shell">
      <section className="auth-stage-shell">
        <div className="auth-stage-intro">
          <p className="eyebrow">Pantry</p>
          <h1>Choose a new password</h1>
          <p className="lede">
            Password reset links expire automatically and can only be used once.
          </p>
        </div>
        {token && tokenStatus?.is_valid ? (
          <ResetPasswordForm token={token} />
        ) : (
          <section className="panel form-panel">
            <p className="eyebrow">Password Reset</p>
            <h1>Reset link unavailable</h1>
            <p className="section-copy">
              {tokenStatus?.reason ?? "This password reset link is missing or invalid."}
            </p>
            <p className="section-copy">
              Request a fresh reset link if you still need to change your password.
            </p>
            <a href="/forgot-password" className="inline-link">
              Request a new reset link
            </a>
          </section>
        )}
      </section>
    </main>
  );
}

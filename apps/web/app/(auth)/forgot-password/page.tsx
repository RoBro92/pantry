import { ForgotPasswordForm } from "../../../components/forgot-password-form";
import { getPasswordResetAvailability, getSession } from "../../../lib/server-auth";
import { redirect } from "next/navigation";

export default async function ForgotPasswordPage() {
  const [session, passwordResetAvailability] = await Promise.all([
    getSession(),
    getPasswordResetAvailability()
  ]);
  if (session) {
    redirect("/app/settings");
  }

  return (
    <main className="page-shell">
      <section className="auth-stage-shell">
        <div className="auth-stage-intro">
          <p className="eyebrow">Pantro</p>
          <h1>Password reset</h1>
          <p className="lede">
            Ask Pantro to send a reset link only if this install has email delivery configured and
            your account uses an email address.
          </p>
        </div>
        {passwordResetAvailability.is_available ? (
          <ForgotPasswordForm />
        ) : (
          <section className="panel form-panel">
            <p className="eyebrow">Password Reset</p>
            <h1>Reset unavailable</h1>
            <p className="section-copy">
              {passwordResetAvailability.reason ??
                "This Pantro install is not ready to send password reset emails."}
            </p>
          </section>
        )}
      </section>
    </main>
  );
}

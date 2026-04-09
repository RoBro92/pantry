import { AccountSettingsForm } from "../../../../components/account-settings-form";
import { PasswordChangeForm } from "../../../../components/password-change-form";
import { getPasswordResetAvailability, requireSession } from "../../../../lib/server-auth";
import { looksLikeEmailAddress } from "../../../../lib/user-identifiers";

export default async function AccountSettingsPage() {
  const session = await requireSession();
  const passwordResetAvailability = await getPasswordResetAvailability();
  const hasEmailAddress = looksLikeEmailAddress(session.user.email);

  return (
    <div className="stack">
      <section className="panel">
        <p className="eyebrow">Account</p>
        <h1>Settings</h1>
        <p className="section-copy">
          Manage your own sign-in details here. Roles and household memberships remain admin-led.
        </p>
        <div className="content-grid">
          <article className="status-card">
            <p className="eyebrow">Signed in as</p>
            <h2>{session.user.display_name ?? session.user.email}</h2>
            <p>{session.user.email}</p>
          </article>
          <article className="status-card">
            <p className="eyebrow">Self-service reset</p>
            <h2>
              {hasEmailAddress && passwordResetAvailability.is_available ? "Available" : "Limited"}
            </h2>
            <p>
              {hasEmailAddress
                ? passwordResetAvailability.is_available
                  ? "Forgot password is available from the sign-in page."
                  : passwordResetAvailability.reason ?? "Password reset is not available right now."
                : "This account uses a username-only sign-in and still needs an admin-led reset."}
            </p>
          </article>
        </div>
      </section>

      <AccountSettingsForm
        email={session.user.email}
        displayName={session.user.display_name}
      />

      <PasswordChangeForm />
    </div>
  );
}

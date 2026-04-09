"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import type { SessionResponse } from "../lib/api-types";
import { patchToApi } from "../lib/client-api";

type AccountSettingsFormProps = {
  email: string;
  displayName: string | null;
};

export function AccountSettingsForm({ email, displayName }: AccountSettingsFormProps) {
  const router = useRouter();
  const [identifier, setIdentifier] = useState(email);
  const [nextDisplayName, setNextDisplayName] = useState(displayName ?? "");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError(null);
    setStatusMessage(null);

    try {
      const session = await patchToApi<SessionResponse>("/api/auth/profile", {
        email: identifier,
        display_name: nextDisplayName.trim() || null,
      });
      setIdentifier(session.user.email);
      setNextDisplayName(session.user.display_name ?? "");
      setStatusMessage("Account details updated.");
      router.refresh();
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : "Could not update account details.",
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <form className="panel stack" onSubmit={handleSubmit} data-testid="account-settings-form">
      <div className="stack compact-stack">
        <p className="eyebrow">Profile</p>
        <h2>Edit account details</h2>
        <p className="section-copy">
          Update your own sign-in identifier and display name. Household access and roles stay
          admin-managed.
        </p>
      </div>
      <div className="content-grid">
        <label className="field">
          <span>Username or email</span>
          <input
            value={identifier}
            onChange={(event) => setIdentifier(event.target.value)}
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
            required
          />
        </label>
        <label className="field">
          <span>Display name</span>
          <input
            value={nextDisplayName}
            onChange={(event) => setNextDisplayName(event.target.value)}
            placeholder="Alex"
          />
        </label>
      </div>
      {error ? <p className="error-text">{error}</p> : null}
      {statusMessage ? <p className="status-note">{statusMessage}</p> : null}
      <div className="page-actions">
        <button type="submit" className="primary-button" disabled={pending}>
          {pending ? "Saving..." : "Save account details"}
        </button>
      </div>
    </form>
  );
}

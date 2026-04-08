"use client";

import { FormEvent, useMemo, useState } from "react";
import { postToApi } from "../lib/client-api";
import type { PasswordActionResponse } from "../lib/api-types";

function validatePasswordDraft(currentPassword: string, newPassword: string, confirmPassword: string) {
  if (!currentPassword) {
    return "Enter your current password.";
  }
  if (newPassword.length < 8) {
    return "New passwords must be at least 8 characters.";
  }
  if (newPassword !== confirmPassword) {
    return "Password confirmation must match.";
  }
  if (currentPassword === newPassword) {
    return "Choose a new password that is different from your current one.";
  }
  return null;
}

export function PasswordChangeForm() {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const validationError = useMemo(
    () => validatePasswordDraft(currentPassword, newPassword, confirmPassword),
    [confirmPassword, currentPassword, newPassword]
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setStatusMessage(null);

    if (validationError) {
      setError(validationError);
      return;
    }

    setPending(true);
    try {
      const response = await postToApi<PasswordActionResponse>("/api/auth/password/change", {
        current_password: currentPassword,
        new_password: newPassword
      });
      setStatusMessage(response.message);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not change password.");
    } finally {
      setPending(false);
    }
  }

  return (
    <form className="panel stack" onSubmit={handleSubmit} data-testid="password-change-form">
      <div className="stack compact-stack">
        <p className="eyebrow">Account Security</p>
        <h2>Change password</h2>
        <p className="section-copy">
          Confirm your current password before setting a new one.
        </p>
      </div>
      <div className="content-grid">
        <label className="field">
          <span>Current password</span>
          <input
            type="password"
            value={currentPassword}
            autoComplete="current-password"
            onChange={(event) => setCurrentPassword(event.target.value)}
            required
          />
        </label>
        <label className="field">
          <span>New password</span>
          <input
            type="password"
            value={newPassword}
            autoComplete="new-password"
            onChange={(event) => setNewPassword(event.target.value)}
            minLength={8}
            required
          />
        </label>
        <label className="field">
          <span>Confirm new password</span>
          <input
            type="password"
            value={confirmPassword}
            autoComplete="new-password"
            onChange={(event) => setConfirmPassword(event.target.value)}
            minLength={8}
            required
          />
        </label>
      </div>
      {error ? <p className="error-text">{error}</p> : null}
      {!error && validationError ? <p className="helper-text is-error">{validationError}</p> : null}
      {statusMessage ? <p className="status-note">{statusMessage}</p> : null}
      <div className="page-actions">
        <button type="submit" className="primary-button" disabled={pending}>
          {pending ? "Updating..." : "Update password"}
        </button>
      </div>
    </form>
  );
}

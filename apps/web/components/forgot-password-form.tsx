"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import type { PasswordActionResponse } from "../lib/api-types";
import { postToApi } from "../lib/client-api";

export function ForgotPasswordForm() {
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setStatusMessage(null);
    setPending(true);

    const formData = new FormData(event.currentTarget);
    try {
      const response = await postToApi<PasswordActionResponse>("/api/auth/password-reset/request", {
        email: String(formData.get("email") ?? "")
      });
      setStatusMessage(response.message);
      event.currentTarget.reset();
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : "Could not request a password reset."
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <form className="panel form-panel" onSubmit={handleSubmit} data-testid="forgot-password-form">
      <p className="eyebrow">Password Reset</p>
      <h1>Reset your password</h1>
      <p className="section-copy">
        Enter the email address tied to your Pantry account. Accounts that only use a username
        still need an admin-led reset.
      </p>
      <label className="field">
        <span>Email address</span>
        <input
          type="email"
          name="email"
          autoComplete="email"
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
          required
        />
      </label>
      {error ? <p className="error-text">{error}</p> : null}
      {statusMessage ? <p className="status-note">{statusMessage}</p> : null}
      <div className="wizard-actions login-actions">
        <button type="submit" className="primary-button" disabled={pending}>
          {pending ? "Sending..." : "Send reset link"}
        </button>
      </div>
      <Link href="/login" className="inline-link">
        Back to sign in
      </Link>
    </form>
  );
}

"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useMemo, useState } from "react";
import type { PasswordActionResponse } from "../lib/api-types";
import { postToApi } from "../lib/client-api";

type ResetPasswordFormProps = {
  token: string;
};

function validatePassword(password: string, confirmation: string) {
  if (password.length < 8) {
    return "Passwords must be at least 8 characters.";
  }
  if (password !== confirmation) {
    return "Password confirmation must match.";
  }
  return null;
}

export function ResetPasswordForm({ token }: ResetPasswordFormProps) {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const validationError = useMemo(
    () => validatePassword(password, confirmation),
    [confirmation, password]
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
      const response = await postToApi<PasswordActionResponse>("/api/auth/password-reset/confirm", {
        token,
        password
      });
      setStatusMessage(response.message);
      setPassword("");
      setConfirmation("");
      window.setTimeout(() => {
        router.push("/login?reset=success");
      }, 800);
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : "Could not reset your password."
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <form className="panel form-panel" onSubmit={handleSubmit} data-testid="reset-password-form">
      <p className="eyebrow">Password Reset</p>
      <h1>Choose a new password</h1>
      <p className="section-copy">
        Set a new password for your Pantry account, then sign in again.
      </p>
      <label className="field">
        <span>New password</span>
        <input
          type="password"
          value={password}
          autoComplete="new-password"
          onChange={(event) => setPassword(event.target.value)}
          minLength={8}
          required
        />
      </label>
      <label className="field">
        <span>Confirm new password</span>
        <input
          type="password"
          value={confirmation}
          autoComplete="new-password"
          onChange={(event) => setConfirmation(event.target.value)}
          minLength={8}
          required
        />
      </label>
      {error ? <p className="error-text">{error}</p> : null}
      {!error && validationError ? <p className="helper-text is-error">{validationError}</p> : null}
      {statusMessage ? <p className="status-note">{statusMessage}</p> : null}
      <div className="wizard-actions login-actions">
        <button type="submit" className="primary-button" disabled={pending}>
          {pending ? "Saving..." : "Reset password"}
        </button>
      </div>
      <Link href="/login" className="inline-link">
        Back to sign in
      </Link>
    </form>
  );
}

"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { appConfig } from "../lib/app-config";
import { readApiErrorMessage } from "../lib/client-api";

type LoginFormProps = {
  nextPath?: string;
  canResetPassword?: boolean;
  statusMessage?: string | null;
};

export function LoginForm({
  nextPath = "/app",
  canResetPassword = false,
  statusMessage = null,
}: LoginFormProps) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);

    const formData = new FormData(event.currentTarget);
    const payload = {
      identifier: String(formData.get("identifier") ?? ""),
      password: String(formData.get("password") ?? "")
    };

    const response = await fetch(`${appConfig.apiBaseUrl}/api/auth/login`, {
      method: "POST",
      credentials: "include",
      headers: {
        "content-type": "application/json"
      },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      setError(await readApiErrorMessage(response, "Login failed."));
      setIsSubmitting(false);
      return;
    }

    router.push(nextPath);
    router.refresh();
  }

  return (
    <form className="panel form-panel" onSubmit={handleSubmit} data-testid="login-form">
      <p className="eyebrow">Sign In</p>
      <h1>Pantro login</h1>
      <p className="section-copy">
        Use the account created during setup or one your platform admin has already staged for you.
      </p>
      <label className="field">
        <span>Username or email</span>
        <input
          type="text"
          name="identifier"
          autoComplete="section-login username"
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
          required
        />
      </label>
      <label className="field">
        <span>Password</span>
        <input
          type="password"
          name="password"
          autoComplete="section-login current-password"
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
          required
        />
      </label>
      {canResetPassword ? (
        <p className="helper-text login-helper-row">
          <span>Need help signing in?</span>
          <Link href="/forgot-password" className="inline-link">
            Forgot password?
          </Link>
        </p>
      ) : null}
      {statusMessage ? <p className="status-note">{statusMessage}</p> : null}
      {error ? <p className="error-text">{error}</p> : null}
      <div className="wizard-actions login-actions">
        <button type="submit" className="primary-button" disabled={isSubmitting}>
          {isSubmitting ? "Signing in..." : "Sign in"}
        </button>
      </div>
    </form>
  );
}

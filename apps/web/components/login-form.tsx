"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { appConfig } from "../lib/app-config";
import { readApiErrorMessage } from "../lib/client-api";

type LoginFormProps = {
  nextPath?: string;
};

export function LoginForm({ nextPath = "/app" }: LoginFormProps) {
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
      <h1>Pantry login</h1>
      <p className="section-copy">
        Use the account created during setup or one your platform admin has already staged for you.
      </p>
      <label className="field">
        <span>Username or email</span>
        <input name="identifier" autoComplete="username" required />
      </label>
      <label className="field">
        <span>Password</span>
        <input type="password" name="password" autoComplete="current-password" required />
      </label>
      {error ? <p className="error-text">{error}</p> : null}
      <div className="wizard-actions login-actions">
        <button type="submit" className="primary-button" disabled={isSubmitting}>
          {isSubmitting ? "Signing in..." : "Sign in"}
        </button>
      </div>
    </form>
  );
}

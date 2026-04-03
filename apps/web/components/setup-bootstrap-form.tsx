"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import type { SessionResponse } from "../lib/api-types";
import { postToApi } from "../lib/client-api";

type SetupBootstrapFormProps = {
  nextPath?: string;
};

export function SetupBootstrapForm({ nextPath = "/admin" }: SetupBootstrapFormProps) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSuccess(null);
    setIsSubmitting(true);

    const formData = new FormData(event.currentTarget);
    const password = String(formData.get("password") ?? "");
    const confirmPassword = String(formData.get("confirm_password") ?? "");
    if (password !== confirmPassword) {
      setError("Passwords must match.");
      setIsSubmitting(false);
      return;
    }

    try {
      await postToApi<SessionResponse>("/api/setup/bootstrap-platform-admin", {
        email: String(formData.get("email") ?? ""),
        display_name: String(formData.get("display_name") ?? "").trim() || null,
        password,
      });
      setSuccess("Platform admin created. Redirecting to the installation console...");
      router.push(nextPath);
      router.refresh();
    } catch (submissionError) {
      setError(submissionError instanceof Error ? submissionError.message : "Setup failed.");
      setIsSubmitting(false);
    }
  }

  return (
    <form className="panel form-panel" onSubmit={handleSubmit} data-testid="setup-bootstrap-form">
      <p className="eyebrow">First Run</p>
      <h1>Create the first platform admin</h1>
      <p className="section-copy">
        This runs only once for a fresh installation. The account created here becomes the first
        installation administrator and is signed in immediately.
      </p>
      <label className="field">
        <span>Email</span>
        <input type="email" name="email" autoComplete="email" required />
      </label>
      <label className="field">
        <span>Display name</span>
        <input name="display_name" autoComplete="name" placeholder="Pantry Admin" />
      </label>
      <label className="field">
        <span>Password</span>
        <input type="password" name="password" autoComplete="new-password" minLength={8} required />
      </label>
      <label className="field">
        <span>Confirm password</span>
        <input
          type="password"
          name="confirm_password"
          autoComplete="new-password"
          minLength={8}
          required
        />
      </label>
      {error ? <p className="error-text">{error}</p> : null}
      {success ? <p className="status-note">{success}</p> : null}
      <button type="submit" className="primary-button" disabled={isSubmitting}>
        {isSubmitting ? "Creating admin..." : "Create platform admin"}
      </button>
    </form>
  );
}

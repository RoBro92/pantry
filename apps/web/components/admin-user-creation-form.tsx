"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import type { AdminUserSummary } from "../lib/api-types";
import { postToApi } from "../lib/client-api";

export function AdminUserCreationForm() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSuccess(null);
    setPending(true);

    const form = event.currentTarget;
    const formData = new FormData(form);
    const password = String(formData.get("password") ?? "");
    const confirmPassword = String(formData.get("confirm_password") ?? "");
    if (password !== confirmPassword) {
      setError("Passwords must match.");
      setPending(false);
      return;
    }

    try {
      const created = await postToApi<AdminUserSummary>("/api/platform-admin/users", {
        email: String(formData.get("email") ?? ""),
        display_name: String(formData.get("display_name") ?? "").trim() || null,
        password,
      });
      setSuccess(`Created ${created.email}.`);
      form.reset();
      router.refresh();
      setPending(false);
    } catch (submissionError) {
      setError(submissionError instanceof Error ? submissionError.message : "User creation failed.");
      setPending(false);
    }
  }

  return (
    <form className="panel" onSubmit={handleSubmit} data-testid="admin-create-user-form">
      <p className="eyebrow">Users</p>
      <h2>Create user</h2>
      <p className="section-copy">
        Create a normal user account first, then assign that user to one or more households.
      </p>
      <div className="recipe-form-grid">
        <label className="field">
          <span>Email</span>
          <input type="email" name="email" required />
        </label>
        <label className="field">
          <span>Display name</span>
          <input name="display_name" placeholder="Alex" />
        </label>
      </div>
      <div className="recipe-form-grid">
        <label className="field">
          <span>Password</span>
          <input type="password" name="password" minLength={8} required />
        </label>
        <label className="field">
          <span>Confirm password</span>
          <input type="password" name="confirm_password" minLength={8} required />
        </label>
      </div>
      {error ? <p className="error-text">{error}</p> : null}
      {success ? <p className="status-note">{success}</p> : null}
      <button type="submit" className="primary-button" disabled={pending}>
        {pending ? "Creating..." : "Create user"}
      </button>
    </form>
  );
}

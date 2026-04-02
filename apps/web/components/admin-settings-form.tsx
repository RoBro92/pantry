"use client";

import { useState } from "react";
import type { PublicBaseURLSummary } from "../lib/api-types";
import { putToApi } from "../lib/client-api";

type AdminSettingsFormProps = {
  initialPublicBaseUrl: PublicBaseURLSummary;
};

export function AdminSettingsForm({ initialPublicBaseUrl }: AdminSettingsFormProps) {
  const [summary, setSummary] = useState(initialPublicBaseUrl);
  const [value, setValue] = useState(initialPublicBaseUrl.stored_value ?? "");
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  async function handleSave() {
    setIsSaving(true);
    setStatusMessage(null);

    try {
      const response = await putToApi<PublicBaseURLSummary>(
        "/api/platform-admin/settings/public-base-url",
        {
          public_base_url: value
        }
      );
      setSummary(response);
      setValue(response.stored_value ?? "");
      setStatusMessage("Public browser URL saved.");
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "Save failed.");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="stack">
      <section className="panel">
        <p className="eyebrow">Browser Links</p>
        <h1>Public Base URL</h1>
        <p>
          Pantry uses this base URL when it generates QR links and other browser-facing deep links.
          The effective value currently resolves from <strong>{summary.effective_source}</strong>.
        </p>
        {summary.effective_source === "environment" ? (
          <p className="status-note">
            An environment variable currently overrides the saved database value.
          </p>
        ) : null}
        {statusMessage ? <p className="status-note">{statusMessage}</p> : null}
        <label className="field">
          <span>Saved public browser URL</span>
          <input
            value={value}
            onChange={(event) => setValue(event.target.value)}
            placeholder="https://pantry.example.com"
          />
        </label>
        <div className="page-actions">
          <button type="button" className="primary-button" disabled={isSaving} onClick={handleSave}>
            {isSaving ? "Saving..." : "Save URL"}
          </button>
        </div>
      </section>

      <section className="status-grid">
        <article className="status-card">
          <p className="eyebrow">Effective URL</p>
          <h2>Live value</h2>
          <p>{summary.effective_value}</p>
        </article>
        <article className="status-card">
          <p className="eyebrow">Saved Value</p>
          <h2>{summary.stored_value ? "Stored" : "Unset"}</h2>
          <p>{summary.stored_value ?? "No database override is saved yet."}</p>
        </article>
      </section>
    </div>
  );
}

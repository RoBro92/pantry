"use client";

import Link from "next/link";
import { useState } from "react";
import type { ReleaseCheckResponse } from "../lib/api-types";
import { postToApi } from "../lib/client-api";

type AdminReleaseNotesDialogProps = {
  initialReleaseStatus: ReleaseCheckResponse;
};

export function AdminReleaseNotesDialog({
  initialReleaseStatus,
}: AdminReleaseNotesDialogProps) {
  const [releaseStatus, setReleaseStatus] = useState(initialReleaseStatus);
  const [hidden, setHidden] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const currentRelease = releaseStatus.current_release;
  if (hidden || !releaseStatus.show_whats_new_prompt || !currentRelease) {
    return null;
  }

  async function handleMarkSeen() {
    setPending(true);
    setError(null);
    try {
      const nextStatus = await postToApi<ReleaseCheckResponse>(
        "/api/platform-admin/release-status/mark-seen",
        {},
      );
      setReleaseStatus(nextStatus);
      setHidden(true);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not save review state.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <section
        className="modal-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="whats-new-title"
        data-testid="admin-whats-new-dialog"
      >
        <p className="eyebrow">What Changed</p>
        <h2 id="whats-new-title">Pantry {currentRelease.version} is now running</h2>
        <p className="section-copy">
          Review the latest release notes once, then Pantry will stop prompting this installation
          until the next update.
        </p>
        {currentRelease.changelog_summary ? (
          <div className="info-callout">
            <strong>Release summary</strong>
            <p>{currentRelease.changelog_summary}</p>
          </div>
        ) : null}
        {currentRelease.breaking_change_notes.length > 0 ? (
          <div className="warning-callout">
            <strong>Breaking changes</strong>
            <ul className="callout-list">
              {currentRelease.breaking_change_notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          </div>
        ) : null}
        {error ? <p className="error-text">{error}</p> : null}
        <div className="page-actions">
          <button
            type="button"
            className="primary-button"
            onClick={() => void handleMarkSeen()}
            disabled={pending}
          >
            {pending ? "Saving..." : "Mark as reviewed"}
          </button>
          <Link href="/admin/updates" className="secondary-link" onClick={() => setHidden(true)}>
            Open Updates
          </Link>
          <button type="button" className="ghost-button" onClick={() => setHidden(true)}>
            Review later
          </button>
        </div>
      </section>
    </div>
  );
}

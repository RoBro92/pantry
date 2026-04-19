"use client";

import Link from "next/link";
import { useState } from "react";
import type { ReleaseCheckResponse } from "../lib/api-types";
import { postToApi } from "../lib/client-api";
import { ModalShell } from "./modal-shell";

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
    <ModalShell
      title="What Changed"
      description={`Pantro ${currentRelease.version}`}
      onClose={() => setHidden(true)}
      closeOnBackdropClick={false}
      showCloseButton={false}
      panelClassName="modal-panel release-notes-panel"
    >
      <div aria-labelledby="whats-new-title" data-testid="admin-whats-new-dialog" className="stack">
        <h2 id="whats-new-title">Highlights</h2>
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
      </div>
    </ModalShell>
  );
}

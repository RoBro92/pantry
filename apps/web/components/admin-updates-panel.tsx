"use client";

import { useState } from "react";
import type { ReleaseCheckResponse } from "../lib/api-types";
import { postToApi } from "../lib/client-api";
import { formatAdminDateTime, getReleaseStatusLabel } from "../lib/admin-display";

type AdminUpdatesPanelProps = {
  initialReleaseStatus: ReleaseCheckResponse;
};

function CopyableCommand({ command }: { command: string }) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    await navigator.clipboard.writeText(command);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="command-card">
      <pre>{command}</pre>
      <button type="button" className="ghost-button" onClick={() => void handleCopy()}>
        {copied ? "Copied" : "Copy"}
      </button>
    </div>
  );
}

function ReleaseNotesCard({
  heading,
  release,
  emptyState,
}: {
  heading: string;
  release: ReleaseCheckResponse["latest_release"] | ReleaseCheckResponse["current_release"];
  emptyState: string;
}) {
  return (
    <article className="panel">
      <p className="eyebrow">{heading}</p>
      {release ? (
        <div className="stack">
          <div>
            <h2>{release.release_name ?? release.release_tag}</h2>
            <p className="section-copy">
              {release.release_tag} · published {formatAdminDateTime(release.published_at)}
            </p>
          </div>
          <ul className="detail-list">
            <li>
              <strong>Version</strong>
              <span>{release.version}</span>
            </li>
            <li>
              <strong>Notes source</strong>
              <span>{release.notes_source ?? "Unavailable"}</span>
            </li>
          </ul>
          {release.changelog_summary ? (
            <div className="info-callout">
              <strong>Changelog summary</strong>
              <p>{release.changelog_summary}</p>
            </div>
          ) : null}
          {release.breaking_change_notes.length > 0 ? (
            <div className="warning-callout">
              <strong>Breaking changes</strong>
              <ul className="callout-list">
                {release.breaking_change_notes.map((note) => (
                  <li key={note}>{note}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {release.release_notes_url ? (
            <div className="page-actions">
              <a href={release.release_notes_url} className="secondary-link">
                Open release notes
              </a>
            </div>
          ) : null}
        </div>
      ) : (
        <p className="section-copy">{emptyState}</p>
      )}
    </article>
  );
}

export function AdminUpdatesPanel({ initialReleaseStatus }: AdminUpdatesPanelProps) {
  const [releaseStatus, setReleaseStatus] = useState(initialReleaseStatus);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleMarkSeen() {
    setPending(true);
    setError(null);
    try {
      const nextStatus = await postToApi<ReleaseCheckResponse>(
        "/api/platform-admin/release-status/mark-seen",
        {},
      );
      setReleaseStatus(nextStatus);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not save review state.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="stack">
      <section className="content-grid">
        <article className="panel">
          <p className="eyebrow">Update Status</p>
          <h2>{getReleaseStatusLabel(releaseStatus.status)}</h2>
          <p className="section-copy">{releaseStatus.message ?? "Release metadata checked."}</p>
          <ul className="detail-list">
            <li>
              <strong>Current version</strong>
              <span>{releaseStatus.current_version}</span>
            </li>
            <li>
              <strong>Latest available version</strong>
              <span>{releaseStatus.latest_version ?? "Unavailable"}</span>
            </li>
            <li>
              <strong>Repository</strong>
              <span>{releaseStatus.repository ?? "Unavailable"}</span>
            </li>
            <li>
              <strong>Checked</strong>
              <span>{formatAdminDateTime(releaseStatus.checked_at)}</span>
            </li>
            <li>
              <strong>Notes reviewed for</strong>
              <span>{releaseStatus.notes_seen_version ?? "Not marked yet"}</span>
            </li>
          </ul>
        </article>

        <article className="panel">
          <p className="eyebrow">Update Strategy</p>
          <h2>Manual Update</h2>
          <p className="section-copy">
            Operator-controlled only. {releaseStatus.source_strategy}
          </p>
          <ul className="detail-list">
            <li>
              <strong>Primary source</strong>
              <span>{releaseStatus.source_type ?? "Unavailable"}</span>
            </li>
            <li>
              <strong>Metadata state</strong>
              <span>{releaseStatus.metadata_status}</span>
            </li>
            <li>
              <strong>Latest release tag</strong>
              <span>{releaseStatus.release_tag ?? "Unavailable"}</span>
            </li>
            <li>
              <strong>Published</strong>
              <span>{formatAdminDateTime(releaseStatus.published_at)}</span>
            </li>
          </ul>
        </article>
      </section>

      {releaseStatus.current_release && releaseStatus.show_whats_new_prompt ? (
        <section className="panel">
          <p className="eyebrow">Review State</p>
          <h2>Current version notes still need acknowledgement</h2>
          <p className="section-copy">
            Mark the running version notes as reviewed once you have checked the changelog and any
            operator actions.
          </p>
          {error ? <p className="error-text">{error}</p> : null}
          <div className="page-actions">
            <button
              type="button"
              className="primary-button"
              onClick={() => void handleMarkSeen()}
              disabled={pending}
            >
              {pending ? "Saving..." : "Mark current notes as reviewed"}
            </button>
          </div>
        </section>
      ) : null}

      <section className="content-grid">
        <ReleaseNotesCard
          heading="Current Release"
          release={releaseStatus.current_release}
          emptyState="This running version does not currently have a published GitHub Release entry to display."
        />
        <ReleaseNotesCard
          heading="Latest Available Release"
          release={releaseStatus.latest_release}
          emptyState="Pantry could not load latest release metadata right now."
        />
      </section>

      <section className="panel">
        <p className="eyebrow">Manual Update Commands</p>
        <h2>Copy and run as the operator</h2>
        <p className="section-copy">
          Pantry does not self-update. Pull the release, restart the stack, and run migrations
          deliberately.
        </p>
        <div className="stack">
          {releaseStatus.manual_update_commands.map((command) => (
            <CopyableCommand key={command} command={command} />
          ))}
        </div>
      </section>
    </div>
  );
}

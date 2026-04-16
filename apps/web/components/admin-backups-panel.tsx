"use client";

import { FormEvent, useMemo, useState } from "react";
import type {
  AdminHouseholdSummary,
  BackupRestoreResponse,
  StagedBackupResponse,
} from "../lib/api-types";
import { appConfig } from "../lib/app-config";
import { postFormToApi, postToApi, readApiErrorMessage } from "../lib/client-api";

const RESTORE_CONFIRMATION_PHRASE = "RESTORE PANTRY INSTANCE";

type AdminBackupsPanelProps = {
  households: AdminHouseholdSummary[];
};

function formatBytes(value: number) {
  if (value < 1024) {
    return `${value} B`;
  }
  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(1)} KB`;
  }
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function parseDownloadFilename(header: string | null) {
  const match = header?.match(/filename="([^"]+)"/i);
  return match?.[1] ?? "pantry-backup.json";
}

export function AdminBackupsPanel({ households }: AdminBackupsPanelProps) {
  const [selectedHousehold, setSelectedHousehold] = useState(households[0]?.external_id ?? "");
  const [pendingExport, setPendingExport] = useState<string | null>(null);
  const [uploadPending, setUploadPending] = useState(false);
  const [restorePending, setRestorePending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [stagedBackup, setStagedBackup] = useState<StagedBackupResponse | null>(null);
  const [confirmationPhrase, setConfirmationPhrase] = useState("");

  const selectedHouseholdSummary = useMemo(
    () => households.find((household) => household.external_id === selectedHousehold) ?? null,
    [households, selectedHousehold],
  );

  async function downloadBackup(path: string, pendingKey: string) {
    setPendingExport(pendingKey);
    setError(null);
    setStatusMessage(null);
    try {
      const response = await fetch(`${appConfig.apiBaseUrl}${path}`, {
        credentials: "include",
      });
      if (!response.ok) {
        throw new Error(await readApiErrorMessage(response));
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = parseDownloadFilename(response.headers.get("content-disposition"));
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      setStatusMessage("Backup export prepared.");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Backup export failed.");
    } finally {
      setPendingExport(null);
    }
  }

  async function handleRestoreUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setUploadPending(true);
    setError(null);
    setStatusMessage(null);
    try {
      const formData = new FormData(event.currentTarget);
      const staged = await postFormToApi<StagedBackupResponse>(
        "/api/platform-admin/backups/restore-upload",
        formData,
      );
      setStagedBackup(staged);
      setConfirmationPhrase("");
      setStatusMessage("Backup uploaded and staged in quarantine.");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Restore upload failed.");
    } finally {
      setUploadPending(false);
    }
  }

  async function handleRestore() {
    if (!stagedBackup) {
      return;
    }

    setRestorePending(true);
    setError(null);
    setStatusMessage(null);
    try {
      const response = await postToApi<BackupRestoreResponse>("/api/platform-admin/backups/restore", {
        stage_id: stagedBackup.stage_id,
        confirmation_phrase: confirmationPhrase,
      });
      setStatusMessage(response.message);
      window.setTimeout(() => {
        window.location.assign("/login");
      }, 1200);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Restore failed.");
    } finally {
      setRestorePending(false);
    }
  }

  return (
    <div className="stack">
      <section className="content-grid">
        <article className="panel">
          <p className="eyebrow">Full</p>
          <h2>Full instance backup</h2>
          <p className="section-copy">
            Export a Pantro native JSON bundle containing the full instance database content for
            system admin controlled recovery.
          </p>
          <div className="page-actions">
            <button
              type="button"
              className="primary-button"
              onClick={() => void downloadBackup("/api/platform-admin/backups/export/instance", "instance")}
              disabled={pendingExport !== null}
            >
              {pendingExport === "instance" ? "Preparing..." : "Download full backup"}
            </button>
          </div>
        </article>

        <article className="panel">
          <p className="eyebrow">Partial</p>
          <h2>Household pantry backup</h2>
          <p className="section-copy">
            Export a single household snapshot for system admin retention. Restore currently supports
            full instance bundles only.
          </p>
          <label className="field">
            <span>Household</span>
            <select
              value={selectedHousehold}
              onChange={(event) => setSelectedHousehold(event.target.value)}
            >
              <option value="">Select a household</option>
              {households.map((household) => (
                <option key={household.external_id} value={household.external_id}>
                  {household.name}
                </option>
              ))}
            </select>
          </label>
          <div className="page-actions">
            <button
              type="button"
              className="secondary-link"
              onClick={() =>
                void downloadBackup(
                  `/api/platform-admin/backups/export/households/${selectedHousehold}`,
                  "household",
                )
              }
              disabled={pendingExport !== null || !selectedHousehold}
            >
              {pendingExport === "household" ? "Preparing..." : "Download household backup"}
            </button>
          </div>
          {selectedHouseholdSummary ? (
            <p className="helper-text">
              Includes household data for {selectedHouseholdSummary.name} and its recorded pantry,
              recipe, import, membership, and audit rows.
            </p>
          ) : null}
        </article>
      </section>

      <section className="panel">
        <p className="eyebrow">Restore</p>
        <h2>Import a full instance backup</h2>
        <p className="section-copy">
          Supported format: Pantro backup bundle v1 JSON. Uploads are validated, staged in
          quarantine, and never executed as code.
        </p>
        <div className="warning-callout">
          <strong>Destructive action</strong>
          <p>
            Restoring a full instance backup replaces the current Pantro database content. After
            restore, sign in again and verify households, users, and settings.
          </p>
        </div>
        <form className="stack" onSubmit={handleRestoreUpload}>
          <label className="field">
            <span>Backup file</span>
            <input type="file" name="file" accept=".json,application/json" required />
          </label>
          <div className="page-actions">
            <button type="submit" className="primary-button" disabled={uploadPending}>
              {uploadPending ? "Uploading..." : "Upload and validate"}
            </button>
          </div>
        </form>

        {stagedBackup ? (
          <div className="stack">
            <div className="info-callout">
              <strong>Staged backup</strong>
              <p>
                {stagedBackup.original_filename} · {formatBytes(stagedBackup.size_bytes)} · scope{" "}
                {stagedBackup.bundle.scope} · schema {stagedBackup.bundle.schema_revision ?? "unknown"}
              </p>
            </div>
            <ul className="callout-list">
              {stagedBackup.warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
            <label className="field">
              <span>Type {RESTORE_CONFIRMATION_PHRASE} to continue</span>
              <input
                type="text"
                value={confirmationPhrase}
                onChange={(event) => setConfirmationPhrase(event.target.value)}
                placeholder={RESTORE_CONFIRMATION_PHRASE}
              />
            </label>
            <div className="page-actions">
              <button
                type="button"
                className="primary-button"
                onClick={() => void handleRestore()}
                disabled={
                  restorePending ||
                  !stagedBackup.supported_for_restore ||
                  confirmationPhrase !== RESTORE_CONFIRMATION_PHRASE
                }
              >
                {restorePending ? "Restoring..." : "Restore full backup"}
              </button>
            </div>
          </div>
        ) : null}
      </section>

      {error ? <p className="error-text">{error}</p> : null}
      {statusMessage ? <p className="status-note">{statusMessage}</p> : null}
    </div>
  );
}

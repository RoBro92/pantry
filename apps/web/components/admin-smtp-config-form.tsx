"use client";

import { useState } from "react";
import type { SMTPConfigResponse, SMTPTestResponse } from "../lib/api-types";
import { postToApi, putToApi } from "../lib/client-api";

type AdminSMTPConfigFormProps = {
  initialConfig: SMTPConfigResponse;
};

export function AdminSMTPConfigForm({ initialConfig }: AdminSMTPConfigFormProps) {
  const [config, setConfig] = useState(initialConfig);
  const [host, setHost] = useState(initialConfig.stored.host ?? "");
  const [port, setPort] = useState(initialConfig.stored.port ? String(initialConfig.stored.port) : "");
  const [username, setUsername] = useState(initialConfig.stored.username ?? "");
  const [password, setPassword] = useState("");
  const [fromEmail, setFromEmail] = useState(initialConfig.stored.from_email ?? "");
  const [fromName, setFromName] = useState(initialConfig.stored.from_name ?? "");
  const [security, setSecurity] = useState(initialConfig.stored.security ?? "starttls");
  const [isEnabled, setIsEnabled] = useState(initialConfig.stored.is_enabled);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState(false);

  async function handleSave() {
    setIsSaving(true);
    setStatusMessage(null);

    try {
      const response = await putToApi<SMTPConfigResponse>("/api/platform-admin/smtp", {
        host: host || null,
        port: port ? Number(port) : null,
        username: username || null,
        password: password || null,
        from_email: fromEmail || null,
        from_name: fromName || null,
        security,
        is_enabled: isEnabled
      });
      setConfig(response);
      setPassword("");
      setStatusMessage("SMTP configuration saved.");
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "Save failed.");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleTest() {
    setIsTesting(true);
    setStatusMessage(null);

    try {
      const response = await postToApi<SMTPTestResponse>("/api/platform-admin/smtp/test", {});
      setConfig(response.config);
      setStatusMessage(response.ok ? "SMTP connectivity test passed." : response.message ?? "SMTP test failed.");
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "SMTP test failed.");
    } finally {
      setIsTesting(false);
    }
  }

  return (
    <div className="stack">
      <section className="panel">
        <p className="eyebrow">Instance SMTP</p>
        <h1>SMTP Foundation</h1>
        <p>
          This stores installation-level SMTP readiness for future recovery and notification flows.
          Passwords are saved encrypted at rest and are never returned in plaintext after save.
        </p>
        {config.effective_source === "environment" ? (
          <p className="status-note">
            Environment variables currently override the saved database configuration.
          </p>
        ) : null}
        {statusMessage ? <p className="status-note">{statusMessage}</p> : null}
        <div className="content-grid">
          <label className="field">
            <span>Host</span>
            <input value={host} onChange={(event) => setHost(event.target.value)} placeholder="smtp.example.com" />
          </label>
          <label className="field">
            <span>Port</span>
            <input value={port} onChange={(event) => setPort(event.target.value)} placeholder="587" />
          </label>
          <label className="field">
            <span>Security</span>
            <select value={security} onChange={(event) => setSecurity(event.target.value)}>
              <option value="starttls">STARTTLS</option>
              <option value="ssl">SSL/TLS</option>
              <option value="none">None</option>
            </select>
          </label>
          <label className="field">
            <span>Username</span>
            <input value={username} onChange={(event) => setUsername(event.target.value)} />
          </label>
          <label className="field">
            <span>Password</span>
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder={config.stored.has_password ? "Stored. Enter a new password to replace it." : ""}
            />
          </label>
          <label className="field">
            <span>From email</span>
            <input value={fromEmail} onChange={(event) => setFromEmail(event.target.value)} placeholder="pantry@example.com" />
          </label>
          <label className="field">
            <span>From name</span>
            <input value={fromName} onChange={(event) => setFromName(event.target.value)} placeholder="Pantry" />
          </label>
        </div>
        <label className="checkbox-row">
          <input type="checkbox" checked={isEnabled} onChange={(event) => setIsEnabled(event.target.checked)} />
          <span>Enable SMTP for future email-capable flows once those features land.</span>
        </label>
        <div className="page-actions">
          <button type="button" className="primary-button" disabled={isSaving} onClick={handleSave}>
            {isSaving ? "Saving..." : "Save SMTP"}
          </button>
          <button
            type="button"
            className="ghost-button"
            disabled={isTesting || !config.configured}
            onClick={handleTest}
          >
            {isTesting ? "Testing..." : "Run connectivity test"}
          </button>
        </div>
      </section>

      <section className="status-grid">
        <article className="status-card">
          <p className="eyebrow">Effective Config</p>
          <h2>{config.configured ? "Configured" : "Not ready"}</h2>
          <p>
            {config.effective.host
              ? `${config.effective.host}:${config.effective.port} · ${config.effective.security}`
              : "No effective SMTP host is configured."}
          </p>
        </article>
        <article className="status-card">
          <p className="eyebrow">Credentials</p>
          <h2>{config.effective.has_password ? "Stored" : "Missing"}</h2>
          <p>
            {config.effective.username
              ? `${config.effective.username} · password ${config.effective.has_password ? "present" : "missing"}`
              : "Anonymous SMTP or incomplete credentials."}
          </p>
        </article>
        <article className="status-card">
          <p className="eyebrow">Last Test</p>
          <h2>{config.last_test_status}</h2>
          <p>{config.last_test_error ?? "No SMTP test has been recorded yet."}</p>
        </article>
      </section>
    </div>
  );
}

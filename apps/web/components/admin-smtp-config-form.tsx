"use client";

import { useState } from "react";
import type { SMTPConfigResponse, SMTPTestResponse } from "../lib/api-types";
import { getConfigSourceLabel } from "../lib/admin-display";
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
  const [passwordResetEnabled, setPasswordResetEnabled] = useState(
    initialConfig.password_reset.is_enabled
  );
  const [passwordResetSubject, setPasswordResetSubject] = useState(
    initialConfig.password_reset.template.subject
  );
  const [passwordResetBody, setPasswordResetBody] = useState(
    initialConfig.password_reset.template.body_template
  );
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
        is_enabled: isEnabled,
        password_reset_enabled: passwordResetEnabled,
        password_reset_subject_template: passwordResetSubject,
        password_reset_body_template: passwordResetBody
      });
      setConfig(response);
      setHost(response.stored.host ?? "");
      setPort(response.stored.port ? String(response.stored.port) : "");
      setUsername(response.stored.username ?? "");
      setFromEmail(response.stored.from_email ?? "");
      setFromName(response.stored.from_name ?? "");
      setSecurity(response.stored.security ?? "starttls");
      setIsEnabled(response.stored.is_enabled);
      setPasswordResetEnabled(response.password_reset.is_enabled);
      setPasswordResetSubject(response.password_reset.template.subject);
      setPasswordResetBody(response.password_reset.template.body_template);
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
        <h1>SMTP and password reset email</h1>
        <p>
          Configure Pantry’s instance-level outbound email. Passwords are saved encrypted at rest
          and never returned in plaintext after save.
        </p>
        <p className="section-copy">
          Effective source: <strong>{getConfigSourceLabel(config.effective_source)}</strong>
        </p>
        {config.effective_source === "environment" ? (
          <p className="status-note">
            Environment variables currently override the saved database configuration.
          </p>
        ) : null}
        {config.config_error ? <p className="error-text">{config.config_error}</p> : null}
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
          <input
            type="checkbox"
            checked={isEnabled}
            onChange={(event) => {
              setIsEnabled(event.target.checked);
              if (!event.target.checked) {
                setPasswordResetEnabled(false);
              }
            }}
          />
          <span>Enable SMTP for Pantry’s product-facing email flows.</span>
        </label>
        <div className="modal-form-section">
          <div className="stack compact-stack">
            <h2>Password reset email</h2>
            <p className="helper-text">
              Self-service reset stays hidden until SMTP is enabled, configured, and has passed a
              connectivity test.
            </p>
          </div>
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={passwordResetEnabled}
              disabled={!isEnabled}
              onChange={(event) => setPasswordResetEnabled(event.target.checked)}
            />
            <span>Allow Pantry to send password reset links.</span>
          </label>
          <label className="field">
            <span>Email subject</span>
            <input
              value={passwordResetSubject}
              onChange={(event) => setPasswordResetSubject(event.target.value)}
            />
          </label>
          <label className="field">
            <span>Body template</span>
            <textarea
              rows={8}
              value={passwordResetBody}
              onChange={(event) => setPasswordResetBody(event.target.value)}
            />
          </label>
          <p className="helper-text">
            Include <code>{"{{reset_link}}"}</code> so the email can send a working reset link.
          </p>
          {config.password_reset.is_available ? (
            <p className="status-note">Password reset emails are ready to use.</p>
          ) : (
            <p className="helper-text is-error">
              {config.password_reset.unavailable_reason ??
                "Password reset emails are not available yet."}
            </p>
          )}
        </div>
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
        <article className="status-card">
          <p className="eyebrow">Password Reset</p>
          <h2>{config.password_reset.is_available ? "Ready" : "Not ready"}</h2>
          <p>
            {config.password_reset.unavailable_reason ??
              "Password reset emails are enabled and ready for the sign-in page."}
          </p>
        </article>
      </section>
    </div>
  );
}

"use client";

import { useMemo, useState } from "react";
import type {
  SMTPConfigResponse,
  SMTPTemplateSummary,
  SMTPTestEmailResponse,
  SMTPTestResponse,
} from "../lib/api-types";
import { getConfigSourceLabel } from "../lib/admin-display";
import { postToApi, putToApi } from "../lib/client-api";
import { ModalShell } from "./modal-shell";

type AdminSMTPConfigFormProps = {
  initialConfig: SMTPConfigResponse;
};

type TemplateModalState = {
  key: string;
  label: string;
  subject: string;
  bodyTemplate: string;
  isEnabled: boolean;
} | null;

function getTemplateStatusClass(template: SMTPTemplateSummary) {
  return template.is_enabled ? "pill smtp-template-pill is-success" : "pill smtp-template-pill is-danger";
}

export function AdminSMTPConfigForm({ initialConfig }: AdminSMTPConfigFormProps) {
  const [config, setConfig] = useState(initialConfig);
  const [host, setHost] = useState(initialConfig.stored.host ?? "");
  const [port, setPort] = useState(initialConfig.stored.port ? String(initialConfig.stored.port) : "");
  const [username, setUsername] = useState(initialConfig.stored.username ?? "");
  const [password, setPassword] = useState("");
  const [fromEmail, setFromEmail] = useState(initialConfig.stored.from_email ?? "");
  const [fromName, setFromName] = useState(initialConfig.stored.from_name ?? "");
  const [testRecipientEmail, setTestRecipientEmail] = useState(initialConfig.test_recipient_email ?? "");
  const [security, setSecurity] = useState(initialConfig.stored.security ?? "starttls");
  const [isEnabled, setIsEnabled] = useState(initialConfig.stored.is_enabled);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [templateMessage, setTemplateMessage] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [isSendingTestEmail, setIsSendingTestEmail] = useState(false);
  const [templatePending, setTemplatePending] = useState(false);
  const [templateToggleKey, setTemplateToggleKey] = useState<string | null>(null);
  const [templateModal, setTemplateModal] = useState<TemplateModalState>(null);

  const passwordResetTemplate = useMemo(
    () => config.templates.find((template) => template.key === "password_reset") ?? null,
    [config.templates],
  );

  function syncConfig(nextConfig: SMTPConfigResponse) {
    setConfig(nextConfig);
    setHost(nextConfig.stored.host ?? "");
    setPort(nextConfig.stored.port ? String(nextConfig.stored.port) : "");
    setUsername(nextConfig.stored.username ?? "");
    setFromEmail(nextConfig.stored.from_email ?? "");
    setFromName(nextConfig.stored.from_name ?? "");
    setTestRecipientEmail(nextConfig.test_recipient_email ?? "");
    setSecurity(nextConfig.stored.security ?? "starttls");
    setIsEnabled(nextConfig.stored.is_enabled);
    setPassword("");
  }

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
        test_recipient_email: testRecipientEmail || null,
        security,
        is_enabled: isEnabled,
      });
      syncConfig(response);
      setStatusMessage("SMTP configuration saved.");
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "Save failed.");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleConnectivityTest() {
    setIsTesting(true);
    setStatusMessage(null);

    try {
      const response = await postToApi<SMTPTestResponse>("/api/platform-admin/smtp/test", {});
      syncConfig(response.config);
      setStatusMessage(response.ok ? "SMTP connectivity test passed." : response.message ?? "SMTP test failed.");
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "SMTP test failed.");
    } finally {
      setIsTesting(false);
    }
  }

  async function handleSendTestEmail() {
    setIsSendingTestEmail(true);
    setStatusMessage(null);

    try {
      const response = await postToApi<SMTPTestEmailResponse>("/api/platform-admin/smtp/test-email", {});
      syncConfig(response.config);
      setStatusMessage(`${response.message} Delivered to ${response.delivered_to}.`);
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "SMTP test email failed.");
    } finally {
      setIsSendingTestEmail(false);
    }
  }

  async function handleSaveTemplate() {
    if (!templateModal) {
      return;
    }

    setTemplatePending(true);
    setTemplateMessage(null);
    try {
      const response = await putToApi<SMTPConfigResponse>(
        `/api/platform-admin/smtp/templates/${templateModal.key}`,
        {
          is_enabled: templateModal.isEnabled,
          subject: templateModal.subject,
          body_template: templateModal.bodyTemplate,
        },
      );
      setConfig(response);
      setTemplateMessage(`${templateModal.label} template saved.`);
      setTemplateModal(null);
    } catch (error) {
      setTemplateMessage(error instanceof Error ? error.message : "Template save failed.");
    } finally {
      setTemplatePending(false);
    }
  }

  async function handleRestoreTemplateDefault() {
    if (!templateModal) {
      return;
    }

    setTemplatePending(true);
    setTemplateMessage(null);
    try {
      const response = await postToApi<SMTPConfigResponse>(
        `/api/platform-admin/smtp/templates/${templateModal.key}/restore-default`,
        {},
      );
      setConfig(response);
      const updatedTemplate = response.templates.find((template) => template.key === templateModal.key);
      if (updatedTemplate) {
        setTemplateModal({
          key: updatedTemplate.key,
          label: updatedTemplate.label,
          subject: updatedTemplate.subject,
          bodyTemplate: updatedTemplate.body_template,
          isEnabled: updatedTemplate.is_enabled,
        });
      }
      setTemplateMessage("Default template restored.");
    } catch (error) {
      setTemplateMessage(error instanceof Error ? error.message : "Could not restore the default template.");
    } finally {
      setTemplatePending(false);
    }
  }

  async function handleRestoreTemplateDefaultFromRow(template: SMTPTemplateSummary) {
    setTemplatePending(true);
    setTemplateMessage(null);
    try {
      const response = await postToApi<SMTPConfigResponse>(
        `/api/platform-admin/smtp/templates/${template.key}/restore-default`,
        {},
      );
      setConfig(response);
      if (templateModal?.key === template.key) {
        const updatedTemplate = response.templates.find((candidate) => candidate.key === template.key);
        if (updatedTemplate) {
          setTemplateModal({
            key: updatedTemplate.key,
            label: updatedTemplate.label,
            subject: updatedTemplate.subject,
            bodyTemplate: updatedTemplate.body_template,
            isEnabled: updatedTemplate.is_enabled,
          });
        }
      }
      setTemplateMessage("Default template restored.");
    } catch (error) {
      setTemplateMessage(error instanceof Error ? error.message : "Could not restore the default template.");
    } finally {
      setTemplatePending(false);
    }
  }

  async function handleToggleTemplate(template: SMTPTemplateSummary) {
    setTemplateToggleKey(template.key);
    setTemplateMessage(null);
    try {
      const response = await postToApi<SMTPConfigResponse>(
        `/api/platform-admin/smtp/templates/${template.key}/toggle`,
        { is_enabled: !template.is_enabled },
      );
      setConfig(response);
      const updatedTemplate = response.templates.find((candidate) => candidate.key === template.key);
      if (updatedTemplate && templateModal?.key === updatedTemplate.key) {
        setTemplateModal({
          key: updatedTemplate.key,
          label: updatedTemplate.label,
          subject: updatedTemplate.subject,
          bodyTemplate: updatedTemplate.body_template,
          isEnabled: updatedTemplate.is_enabled,
        });
      }
      setTemplateMessage(
        `${template.label} ${template.is_enabled ? "disabled" : "enabled"}.`,
      );
    } catch (error) {
      setTemplateMessage(error instanceof Error ? error.message : "Template toggle failed.");
    } finally {
      setTemplateToggleKey(null);
    }
  }

  return (
    <div className="stack">
      <section className="panel">
        <p className="eyebrow">Instance SMTP</p>
        <h1>SMTP</h1>
        <p>Configure Pantro’s instance level outbound email.</p>
        <p className="section-copy">
          Effective source: <strong>{getConfigSourceLabel(config.effective_source)}</strong>
        </p>
        <p className="helper-text">
          Pantro keeps the latest recorded SMTP connectivity result here. It does not background-poll
          SMTP health on a timer.
        </p>
        {config.effective_source === "environment" ? (
          <p className="status-note">
            Environment variables currently override the saved database configuration.
          </p>
        ) : null}
        {config.config_error ? <p className="error-text">{config.config_error}</p> : null}
        {statusMessage ? <p className="status-note">{statusMessage}</p> : null}

        <div className="modal-form-section">
          <div className="stack compact-stack">
            <h2>Connection and sender</h2>
            <p className="helper-text">
              Pantro uses one sender alias for password reset emails, SMTP test emails, and future
              template-driven emails.
            </p>
          </div>
          <div className="content-grid">
            <label className="field">
              <span>Host</span>
              <input
                value={host}
                onChange={(event) => setHost(event.target.value)}
                placeholder="smtp.example.com"
              />
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
              <span>Sender email</span>
              <input
                value={fromEmail}
                onChange={(event) => setFromEmail(event.target.value)}
                placeholder="pantro@example.com"
              />
            </label>
            <label className="field">
              <span>Sender name</span>
              <input value={fromName} onChange={(event) => setFromName(event.target.value)} placeholder="Pantro" />
            </label>
            <label className="field">
              <span>Test recipient email</span>
              <input
                value={testRecipientEmail}
                onChange={(event) => setTestRecipientEmail(event.target.value)}
                placeholder="you@example.com"
              />
            </label>
          </div>
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={isEnabled}
              onChange={(event) => setIsEnabled(event.target.checked)}
            />
            <span>Enable SMTP for Pantro.</span>
          </label>
          <div className="page-actions">
            <button type="button" className="primary-button" disabled={isSaving} onClick={handleSave}>
              {isSaving ? "Saving..." : "Save SMTP"}
            </button>
            <button
              type="button"
              className="ghost-button"
              disabled={isTesting || !config.configured}
              onClick={handleConnectivityTest}
            >
              {isTesting ? "Testing..." : "Run connectivity test"}
            </button>
            <button
              type="button"
              className="ghost-button"
              disabled={isSendingTestEmail || !config.configured || !config.test_recipient_email}
              onClick={handleSendTestEmail}
            >
              {isSendingTestEmail ? "Sending..." : "Send test email"}
            </button>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="stack compact-stack">
          <p className="eyebrow">Templates</p>
          <h2>Email templates</h2>
          <p className="section-copy">
            Manage the current template catalog one row at a time. Disabled templates stay out of
            user-facing auth flows until SMTP is also configured and tested.
          </p>
        </div>
        {templateMessage ? <p className="status-note">{templateMessage}</p> : null}
        <div className="smtp-template-list">
          {config.templates.map((template) => (
            <article key={template.key} className="smtp-template-row">
              <div className="smtp-template-row-main">
                <strong>{template.label}</strong>
                {!template.is_available ? (
                  <span className="helper-text">
                    {template.unavailable_reason ?? "Not ready yet."}
                  </span>
                ) : null}
              </div>
              <div className="smtp-template-row-actions">
                <button
                  type="button"
                  className={getTemplateStatusClass(template)}
                  disabled={templateToggleKey === template.key}
                  onClick={() => void handleToggleTemplate(template)}
                >
                  {templateToggleKey === template.key
                    ? "Saving..."
                    : template.is_enabled
                      ? "Enabled"
                      : "Disabled"}
                </button>
                <button
                  type="button"
                  className="ghost-button compact-button"
                  onClick={() =>
                    setTemplateModal({
                      key: template.key,
                      label: template.label,
                      subject: template.subject,
                      bodyTemplate: template.body_template,
                      isEnabled: template.is_enabled,
                    })
                  }
                >
                  Edit
                </button>
                <button
                  type="button"
                  className="ghost-button compact-button"
                  onClick={() => void handleRestoreTemplateDefaultFromRow(template)}
                  disabled={templatePending}
                >
                  Restore default
                </button>
              </div>
            </article>
          ))}
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

      {templateModal && passwordResetTemplate ? (
        <ModalShell
          title={templateModal.label}
          description="Update the template copy or restore the Pantro default."
          onClose={() => {
            if (!templatePending) {
              setTemplateModal(null);
            }
          }}
        >
          <div className="stack">
            <label className="checkbox-row">
              <input
                type="checkbox"
                checked={templateModal.isEnabled}
                onChange={(event) =>
                  setTemplateModal((current) =>
                    current ? { ...current, isEnabled: event.target.checked } : current,
                  )
                }
              />
              <span>Enable this template.</span>
            </label>
            <label className="field">
              <span>Email subject</span>
              <input
                value={templateModal.subject}
                onChange={(event) =>
                  setTemplateModal((current) =>
                    current ? { ...current, subject: event.target.value } : current,
                  )
                }
              />
            </label>
            <label className="field">
              <span>Body template</span>
              <textarea
                rows={10}
                value={templateModal.bodyTemplate}
                onChange={(event) =>
                  setTemplateModal((current) =>
                    current ? { ...current, bodyTemplate: event.target.value } : current,
                  )
                }
              />
            </label>
            <p className="helper-text">
              Required placeholder: <code>{passwordResetTemplate.required_placeholders.join(", ")}</code>
            </p>
            <div className="page-actions">
              <button
                type="button"
                className="ghost-button"
                onClick={() => void handleRestoreTemplateDefault()}
                disabled={templatePending}
              >
                Restore default
              </button>
              <button
                type="button"
                className="primary-button"
                onClick={() => void handleSaveTemplate()}
                disabled={templatePending}
              >
                {templatePending ? "Saving..." : "Save template"}
              </button>
            </div>
          </div>
        </ModalShell>
      ) : null}
    </div>
  );
}

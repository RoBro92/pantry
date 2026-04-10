import type { ReleaseCheckResponse } from "./api-types";

const CONFIG_SOURCE_LABELS: Record<string, string> = {
  deployment_default: "Default",
  database: "Saved",
  environment: "Environment override"
};

const RELEASE_STATUS_LABELS: Record<ReleaseCheckResponse["status"], string> = {
  update_available: "Update available",
  up_to_date: "Up to date",
  ahead_of_latest_release: "Ahead of latest release",
  comparison_unavailable: "Version unknown",
  release_metadata_missing: "Metadata unavailable",
  unavailable: "Unavailable",
  not_configured: "Not configured"
};

const DEPLOYMENT_MODE_LABELS: Record<string, string> = {
  self_hosted: "Self-hosted",
  demo: "Demo",
  saas: "SaaS"
};

const AI_PROVIDER_LABELS: Record<string, string> = {
  openai: "OpenAI",
  claude: "Claude",
  ollama: "Ollama",
  custom: "Custom",
  openai_compatible: "Custom"
};

export function formatAdminDateTime(value: string | null) {
  if (!value) {
    return "Unavailable";
  }
  return new Date(value).toLocaleString("en-GB", {
    dateStyle: "medium",
    timeStyle: "short"
  });
}

export function formatUptime(totalSeconds: number) {
  const minutes = Math.floor(totalSeconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  if (days > 0) {
    const remainingHours = hours % 24;
    return remainingHours > 0
      ? `${days} day${days === 1 ? "" : "s"} ${remainingHours} hour${remainingHours === 1 ? "" : "s"}`
      : `${days} day${days === 1 ? "" : "s"}`;
  }

  if (hours > 0) {
    const remainingMinutes = minutes % 60;
    return remainingMinutes > 0
      ? `${hours} hour${hours === 1 ? "" : "s"} ${remainingMinutes} minute${remainingMinutes === 1 ? "" : "s"}`
      : `${hours} hour${hours === 1 ? "" : "s"}`;
  }

  return `${Math.max(minutes, 0)} minute${minutes === 1 ? "" : "s"}`;
}

export function formatSecondsAsDuration(value: number | null) {
  if (value === null) {
    return "Unavailable";
  }
  return formatUptime(value);
}

export function formatLatencyMs(value: number | null) {
  if (value === null) {
    return "Unavailable";
  }
  return `${value.toFixed(value >= 10 ? 0 : 2)} ms`;
}

export function getConfigSourceLabel(source: string | null | undefined) {
  if (!source) {
    return "Unavailable";
  }
  return CONFIG_SOURCE_LABELS[source] ?? source;
}

export function getReleaseStatusLabel(status: ReleaseCheckResponse["status"]) {
  return RELEASE_STATUS_LABELS[status];
}

export function getDeploymentModeLabel(mode: string) {
  return DEPLOYMENT_MODE_LABELS[mode] ?? mode;
}

export function getAIProviderLabel(provider: string | null | undefined) {
  if (!provider) {
    return "None";
  }
  return AI_PROVIDER_LABELS[provider] ?? provider;
}

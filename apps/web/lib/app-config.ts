import {
  deploymentModes,
  domainEntities,
  pantryRoles
} from "@pantro/shared-types";

function normalizeBaseUrl(value: string | undefined): string | null {
  const normalized = value?.trim();
  if (!normalized) {
    return null;
  }

  return normalized.endsWith("/") ? normalized.slice(0, -1) : normalized;
}

export const appConfig = {
  name: "Pantro",
  environment: process.env.NODE_ENV ?? "development",
  version: process.env.NEXT_PUBLIC_APP_VERSION ?? "0.0.0-dev",
  apiBaseUrl: normalizeBaseUrl(process.env.NEXT_PUBLIC_API_BASE_URL) ?? "",
  internalApiBaseUrl:
    normalizeBaseUrl(process.env.INTERNAL_API_BASE_URL) ??
    normalizeBaseUrl(process.env.NEXT_PUBLIC_API_BASE_URL) ??
    "http://localhost:8000",
  deploymentModes,
  pantryRoles,
  domainEntities
} as const;

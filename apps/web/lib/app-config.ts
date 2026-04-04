import {
  deploymentModes,
  domainEntities,
  pantryRoles
} from "@pantry/shared-types";

export const appConfig = {
  name: "Pantry",
  environment: process.env.NODE_ENV ?? "development",
  version: process.env.NEXT_PUBLIC_APP_VERSION ?? "0.0.0-dev",
  apiBaseUrl: process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000",
  internalApiBaseUrl:
    process.env.INTERNAL_API_BASE_URL ??
    process.env.NEXT_PUBLIC_API_BASE_URL ??
    "http://localhost:8000",
  deploymentModes,
  pantryRoles,
  domainEntities
} as const;

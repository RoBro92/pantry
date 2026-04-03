import { redirect } from "next/navigation";
import type {
  AIFeatureStatus,
  AIProviderConfigResponse,
  AdminHouseholdSummary,
  AdminOverview,
  AdminUserSummary,
  DiagnosticsResponse,
  ImportDetailResponse,
  ImportListResponse,
  LocationAccessResponse,
  NearExpiryResponse,
  PantryOverview,
  PublicBaseURLSummary,
  RecipeDetailResponse,
  RecipeListResponse,
  SMTPConfigResponse,
  SessionResponse,
  SetupStatusResponse
} from "./api-types";
import { apiGet, apiGetIfOk } from "./server-api";

export async function getSession(): Promise<SessionResponse | null> {
  return apiGetIfOk<SessionResponse>("/api/auth/session");
}

export async function getSetupStatus(): Promise<SetupStatusResponse> {
  return apiGet<SetupStatusResponse>("/api/setup/status");
}

export async function requireSession(): Promise<SessionResponse> {
  const session = await getSession();
  if (!session) {
    redirect("/login");
  }

  return session;
}

export async function requirePlatformAdminSession(): Promise<SessionResponse> {
  const session = await requireSession();
  if (session.user.platform_role !== "platform_admin") {
    redirect("/app");
  }

  return session;
}

export async function getAdminOverview(): Promise<AdminOverview> {
  return apiGet<AdminOverview>("/api/platform-admin/overview");
}

export async function getAdminUsers(): Promise<AdminUserSummary[]> {
  return apiGet<AdminUserSummary[]>("/api/platform-admin/users");
}

export async function getAdminHouseholds(): Promise<AdminHouseholdSummary[]> {
  return apiGet<AdminHouseholdSummary[]>("/api/platform-admin/households");
}

export async function getAIProviderConfig(): Promise<AIProviderConfigResponse> {
  return apiGet<AIProviderConfigResponse>("/api/platform-admin/ai/provider-config");
}

export async function getSMTPConfig(): Promise<SMTPConfigResponse> {
  return apiGet<SMTPConfigResponse>("/api/platform-admin/smtp");
}

export async function getPublicBaseURL(): Promise<PublicBaseURLSummary> {
  return apiGet<PublicBaseURLSummary>("/api/platform-admin/settings/public-base-url");
}

export async function getDiagnostics(): Promise<DiagnosticsResponse> {
  return apiGet<DiagnosticsResponse>("/api/platform-admin/diagnostics");
}

function withQuery(
  path: string,
  params: Record<string, string | null | undefined>
): string {
  const search = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (!value) {
      return;
    }
    search.set(key, value);
  });

  const query = search.toString();
  return query ? `${path}?${query}` : path;
}

export async function getPantryOverview(
  householdExternalId: string,
  params: {
    q?: string | null;
    location_group_external_id?: string | null;
    location_external_id?: string | null;
  } = {}
): Promise<PantryOverview> {
  return apiGet<PantryOverview>(
    withQuery(`/api/households/${householdExternalId}/pantry/overview`, params)
  );
}

export async function getNearExpiry(
  householdExternalId: string,
  days = 14
): Promise<NearExpiryResponse> {
  return apiGet<NearExpiryResponse>(
    withQuery(`/api/households/${householdExternalId}/pantry/near-expiry`, {
      days: String(days)
    })
  );
}

export async function getRecipeList(
  householdExternalId: string
): Promise<RecipeListResponse> {
  return apiGet<RecipeListResponse>(`/api/households/${householdExternalId}/recipes`);
}

export async function getRecipeDetail(
  householdExternalId: string,
  recipeExternalId: string
): Promise<RecipeDetailResponse> {
  return apiGet<RecipeDetailResponse>(
    `/api/households/${householdExternalId}/recipes/${recipeExternalId}`
  );
}

export async function getImportList(
  householdExternalId: string
): Promise<ImportListResponse> {
  return apiGet<ImportListResponse>(`/api/households/${householdExternalId}/imports`);
}

export async function getImportDetail(
  householdExternalId: string,
  importExternalId: string
): Promise<ImportDetailResponse> {
  return apiGet<ImportDetailResponse>(
    `/api/households/${householdExternalId}/imports/${importExternalId}`
  );
}

export async function getHouseholdAIStatus(
  householdExternalId: string
): Promise<AIFeatureStatus> {
  return apiGet<AIFeatureStatus>(`/api/households/${householdExternalId}/ai/status`);
}

export async function getLocationAccess(
  locationRoute: string
): Promise<LocationAccessResponse> {
  return apiGet<LocationAccessResponse>(`/api/locations/${locationRoute}`);
}

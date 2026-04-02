import { redirect } from "next/navigation";
import type {
  AdminHouseholdSummary,
  AdminOverview,
  AdminUserSummary,
  NearExpiryResponse,
  PantryOverview,
  RecipeDetailResponse,
  RecipeListResponse,
  SessionResponse
} from "./api-types";
import { apiGet, apiGetIfOk } from "./server-api";

export async function getSession(): Promise<SessionResponse | null> {
  return apiGetIfOk<SessionResponse>("/api/auth/session");
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

import { redirect } from "next/navigation";
import type {
  AdminHouseholdSummary,
  AdminOverview,
  AdminUserSummary,
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

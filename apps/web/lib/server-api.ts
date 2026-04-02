import { headers } from "next/headers";
import { appConfig } from "./app-config";

export async function apiGet<T>(path: string): Promise<T> {
  const headerStore = await headers();
  const cookie = headerStore.get("cookie");

  const response = await fetch(`${appConfig.internalApiBaseUrl}${path}`, {
    cache: "no-store",
    headers: cookie ? { cookie } : undefined
  });

  if (!response.ok) {
    throw new Error(`API request failed for ${path}: ${response.status}`);
  }

  return (await response.json()) as T;
}

export async function apiGetIfOk<T>(path: string): Promise<T | null> {
  const headerStore = await headers();
  const cookie = headerStore.get("cookie");

  const response = await fetch(`${appConfig.internalApiBaseUrl}${path}`, {
    cache: "no-store",
    headers: cookie ? { cookie } : undefined
  });

  if (response.status === 401) {
    return null;
  }

  if (!response.ok) {
    throw new Error(`API request failed for ${path}: ${response.status}`);
  }

  return (await response.json()) as T;
}


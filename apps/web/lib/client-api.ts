"use client";

import { appConfig } from "./app-config";

type ApiErrorBody = {
  detail?: string;
};

export async function postToApi<T>(path: string, payload: unknown): Promise<T> {
  const response = await fetch(`${appConfig.apiBaseUrl}${path}`, {
    method: "POST",
    credentials: "include",
    headers: {
      "content-type": "application/json"
    },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as ApiErrorBody | null;
    throw new Error(body?.detail ?? "Request failed.");
  }

  return (await response.json()) as T;
}

"use client";

import { appConfig } from "./app-config";

type ApiErrorBody = {
  detail?: string;
};

async function sendToApi<T>(
  method: "POST" | "PUT",
  path: string,
  payload: unknown
): Promise<T> {
  const response = await fetch(`${appConfig.apiBaseUrl}${path}`, {
    method,
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

export async function postToApi<T>(path: string, payload: unknown): Promise<T> {
  return sendToApi("POST", path, payload);
}

export async function putToApi<T>(path: string, payload: unknown): Promise<T> {
  return sendToApi("PUT", path, payload);
}

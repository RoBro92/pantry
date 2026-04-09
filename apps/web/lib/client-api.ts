"use client";

import { appConfig } from "./app-config";

type ApiErrorBody = {
  detail?:
    | string
    | Array<{
        msg?: string;
        loc?: Array<string | number>;
      }>;
};

function formatApiErrorMessage(body: ApiErrorBody | null, fallback: string): string {
  const detail = body?.detail;
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }
  if (Array.isArray(detail) && detail.length > 0) {
    return detail
      .map((item) => {
        const message = item.msg?.trim() || "Invalid value.";
        const location =
          item.loc
            ?.filter((segment) => segment !== "body")
            .map((segment) => String(segment))
            .join(" > ") ?? "";
        return location ? `${location}: ${message}` : message;
      })
      .join(" ");
  }
  return fallback;
}

export async function readApiErrorMessage(
  response: Response,
  fallback = "Request failed."
): Promise<string> {
  const body = (await response.json().catch(() => null)) as ApiErrorBody | null;
  return formatApiErrorMessage(body, fallback);
}

async function sendToApi<T>(
  method: "DELETE" | "PATCH" | "POST" | "PUT",
  path: string,
  payload?: unknown
): Promise<T> {
  const response = await fetch(`${appConfig.apiBaseUrl}${path}`, {
    method,
    credentials: "include",
    headers: {
      "content-type": "application/json"
    },
    body: payload === undefined ? undefined : JSON.stringify(payload)
  });

  if (!response.ok) {
    throw new Error(await readApiErrorMessage(response));
  }

  return (await response.json()) as T;
}

export async function postToApi<T>(path: string, payload: unknown): Promise<T> {
  return sendToApi("POST", path, payload);
}

export async function putToApi<T>(path: string, payload: unknown): Promise<T> {
  return sendToApi("PUT", path, payload);
}

export async function patchToApi<T>(path: string, payload: unknown): Promise<T> {
  return sendToApi("PATCH", path, payload);
}

export async function deleteToApi<T>(path: string): Promise<T> {
  return sendToApi("DELETE", path);
}

export async function postFormToApi<T>(path: string, payload: FormData): Promise<T> {
  const response = await fetch(`${appConfig.apiBaseUrl}${path}`, {
    method: "POST",
    credentials: "include",
    body: payload
  });

  if (!response.ok) {
    throw new Error(await readApiErrorMessage(response));
  }

  return (await response.json()) as T;
}

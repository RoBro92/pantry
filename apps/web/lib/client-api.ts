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
  method: "DELETE" | "GET" | "PATCH" | "POST" | "PUT",
  path: string,
  payload?: unknown
): Promise<T> {
  const init: RequestInit = {
    method,
    credentials: "include",
  };

  if (payload !== undefined) {
    init.headers = {
      "content-type": "application/json"
    };
    init.body = JSON.stringify(payload);
  }

  const response = await fetch(`${appConfig.apiBaseUrl}${path}`, init);

  if (!response.ok) {
    throw new Error(await readApiErrorMessage(response));
  }

  return (await response.json()) as T;
}

export async function getFromApi<T>(path: string): Promise<T> {
  return sendToApi("GET", path);
}

async function sendToApiWithBody<T>(
  method: "DELETE" | "PATCH" | "POST" | "PUT",
  path: string,
  payload?: unknown
): Promise<T> {
  return sendToApi(method, path, payload);
}

export async function postToApi<T>(path: string, payload: unknown): Promise<T> {
  return sendToApiWithBody("POST", path, payload);
}

export async function putToApi<T>(path: string, payload: unknown): Promise<T> {
  return sendToApiWithBody("PUT", path, payload);
}

export async function patchToApi<T>(path: string, payload: unknown): Promise<T> {
  return sendToApiWithBody("PATCH", path, payload);
}

export async function deleteToApi<T>(path: string, payload?: unknown): Promise<T> {
  return sendToApiWithBody("DELETE", path, payload);
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

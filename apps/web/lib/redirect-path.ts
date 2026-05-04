const DEFAULT_INTERNAL_PATH = "/app";
const URL_BASE = "https://pantro.local";

export function getSafeInternalPath(
  value: string | null | undefined,
  fallback = DEFAULT_INTERNAL_PATH
): string {
  if (!value || value.trim() !== value) {
    return fallback;
  }

  if (!value.startsWith("/") || value.startsWith("//")) {
    return fallback;
  }

  if (value.includes("\\") || /^\/%2f/i.test(value) || /%5c/i.test(value)) {
    return fallback;
  }

  try {
    const parsed = new URL(value, URL_BASE);
    if (parsed.origin !== URL_BASE) {
      return fallback;
    }
    return `${parsed.pathname}${parsed.search}${parsed.hash}`;
  } catch {
    return fallback;
  }
}

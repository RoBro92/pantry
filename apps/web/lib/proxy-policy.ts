const allowedForwardHeaders = new Set([
  "accept",
  "accept-language",
  "content-type",
  "cookie",
  "user-agent",
  "x-csrf-token",
  "x-requested-with"
]);

const allowedResponseHeaders = new Set([
  "cache-control",
  "content-disposition",
  "content-length",
  "content-type",
  "etag",
  "expires",
  "last-modified",
  "location",
  "pragma",
  "set-cookie",
  "vary"
]);

const authPaths = new Set(["login", "logout", "profile", "session"]);
const passwordResetPaths = new Set(["confirm", "request", "status", "token-status"]);
const setupWizardPaths = new Set([
  "ai",
  "dietary",
  "finalize",
  "household",
  "mode",
  "public-url",
  "restore-upload",
  "smtp",
  "users",
  "welcome"
]);
const platformAdminRoots = new Set([
  "ai",
  "backups",
  "diagnostics",
  "households",
  "overview",
  "release-status",
  "settings",
  "smtp",
  "users"
]);
const householdRoots = new Set([
  "ai",
  "imports",
  "location-groups",
  "locations",
  "pantry",
  "product-intelligence",
  "products",
  "recipes",
  "shopping-list",
  "stock-lots"
]);
const mutatingMethods = new Set(["DELETE", "PATCH", "POST", "PUT"]);
const systemPaths = new Set(["health", "ready"]);

function hasValidSegments(pathSegments: readonly string[]): boolean {
  return pathSegments.length > 0 && pathSegments.every((segment) => segment.length > 0);
}

function isAllowedAuthPath(pathSegments: readonly string[]): boolean {
  const [, second, third] = pathSegments;

  if (pathSegments.length === 2 && authPaths.has(second)) {
    return true;
  }

  if (pathSegments.length === 3 && second === "password" && third === "change") {
    return true;
  }

  return pathSegments.length === 3 && second === "password-reset" && passwordResetPaths.has(third);
}

function isAllowedSetupPath(pathSegments: readonly string[]): boolean {
  const [, second, third] = pathSegments;

  if (pathSegments.length === 2 && second === "status") {
    return true;
  }

  if (second !== "wizard") {
    return false;
  }

  return pathSegments.length === 2 || (pathSegments.length === 3 && setupWizardPaths.has(third));
}

export function isAllowedProxyPath(pathSegments: readonly string[]): boolean {
  if (!hasValidSegments(pathSegments)) {
    return false;
  }

  const [first, second, third] = pathSegments;

  if (pathSegments.length === 1 && systemPaths.has(first)) {
    return true;
  }

  if (first === "auth") {
    return isAllowedAuthPath(pathSegments);
  }

  if (first === "setup") {
    return isAllowedSetupPath(pathSegments);
  }

  if (first === "platform-admin") {
    return Boolean(second && platformAdminRoots.has(second));
  }

  if (first === "households") {
    return Boolean(second && third && householdRoots.has(third));
  }

  return first === "locations" && pathSegments.length === 2;
}

export function copyAllowedForwardHeaders(headers: Headers): Headers {
  const forwardedHeaders = new Headers();

  headers.forEach((value, key) => {
    if (allowedForwardHeaders.has(key.toLowerCase())) {
      forwardedHeaders.set(key, value);
    }
  });

  return forwardedHeaders;
}

export function copyAllowedResponseHeaders(headers: Headers): Headers {
  const responseHeaders = new Headers();

  headers.forEach((value, key) => {
    if (allowedResponseHeaders.has(key.toLowerCase())) {
      responseHeaders.set(key, value);
    }
  });

  return responseHeaders;
}

function parseOrigin(value: string): string | null {
  try {
    return new URL(value).origin;
  } catch {
    return null;
  }
}

export function isCrossOriginMutation(
  method: string,
  requestOrigin: string,
  originHeader: string | null,
  refererHeader: string | null
): boolean {
  if (!mutatingMethods.has(method.toUpperCase())) {
    return false;
  }

  const expectedOrigin = parseOrigin(requestOrigin);
  if (!expectedOrigin) {
    return true;
  }

  if (originHeader) {
    const origin = parseOrigin(originHeader);
    return origin !== expectedOrigin;
  }

  if (refererHeader) {
    const origin = parseOrigin(refererHeader);
    return origin !== expectedOrigin;
  }

  return false;
}

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import vm from "node:vm";
import ts from "typescript";

const currentDir = path.dirname(fileURLToPath(import.meta.url));

async function loadTypeScriptModule(fileName) {
  const sourcePath = path.join(currentDir, fileName);
  const source = await readFile(sourcePath, "utf8");
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
    },
    fileName: sourcePath
  });
  const module = { exports: {} };
  const context = vm.createContext({
    Headers,
    URL,
    exports: module.exports,
    module,
  });

  vm.runInContext(outputText, context, { filename: sourcePath });
  return module.exports;
}

const redirectPath = await loadTypeScriptModule("redirect-path.ts");
const proxyPolicy = await loadTypeScriptModule("proxy-policy.ts");

test("getSafeInternalPath only accepts single-slash app-internal URLs", () => {
  assert.equal(redirectPath.getSafeInternalPath("/app/households/hh_123?tab=list#top"), "/app/households/hh_123?tab=list#top");
  assert.equal(redirectPath.getSafeInternalPath("/"), "/");
  assert.equal(redirectPath.getSafeInternalPath(undefined), "/app");
  assert.equal(redirectPath.getSafeInternalPath(null), "/app");
  assert.equal(redirectPath.getSafeInternalPath(""), "/app");
  assert.equal(redirectPath.getSafeInternalPath(" /admin", "/fallback"), "/fallback");
  assert.equal(redirectPath.getSafeInternalPath("https://example.test/admin", "/fallback"), "/fallback");
  assert.equal(redirectPath.getSafeInternalPath("//example.test/admin", "/fallback"), "/fallback");
  assert.equal(redirectPath.getSafeInternalPath("/%2Fexample.test/admin", "/fallback"), "/fallback");
  assert.equal(redirectPath.getSafeInternalPath("\\example.test\\admin", "/fallback"), "/fallback");
  assert.equal(redirectPath.getSafeInternalPath("/\\example.test", "/fallback"), "/fallback");
  assert.equal(redirectPath.getSafeInternalPath("/%5Cexample.test", "/fallback"), "/fallback");
});

test("isAllowedProxyPath permits current frontend API namespaces only", () => {
  assert.equal(proxyPolicy.isAllowedProxyPath(["health"]), true);
  assert.equal(proxyPolicy.isAllowedProxyPath(["ready"]), true);
  assert.equal(proxyPolicy.isAllowedProxyPath(["auth", "login"]), true);
  assert.equal(proxyPolicy.isAllowedProxyPath(["auth", "password-reset", "confirm"]), true);
  assert.equal(proxyPolicy.isAllowedProxyPath(["setup", "wizard", "restore-upload"]), true);
  assert.equal(proxyPolicy.isAllowedProxyPath(["platform-admin", "backups", "export", "instance"]), true);
  assert.equal(proxyPolicy.isAllowedProxyPath(["households", "hh_123", "pantry", "entries"]), true);
  assert.equal(proxyPolicy.isAllowedProxyPath(["households", "hh_123", "product-intelligence", "status"]), true);
  assert.equal(proxyPolicy.isAllowedProxyPath(["locations", "loc_123"]), true);

  assert.equal(proxyPolicy.isAllowedProxyPath([]), false);
  assert.equal(proxyPolicy.isAllowedProxyPath(["debug"]), false);
  assert.equal(proxyPolicy.isAllowedProxyPath(["auth", "oauth", "callback"]), false);
  assert.equal(proxyPolicy.isAllowedProxyPath(["households"]), false);
  assert.equal(proxyPolicy.isAllowedProxyPath(["households", "hh_123", "billing"]), false);
  assert.equal(proxyPolicy.isAllowedProxyPath(["locations", "loc_123", "extra"]), false);
});

test("copyAllowedForwardHeaders forwards only API-safe request headers", () => {
  const copied = proxyPolicy.copyAllowedForwardHeaders(
    new Headers({
      accept: "application/json",
      authorization: "Bearer secret",
      connection: "keep-alive",
      "content-type": "application/json",
      cookie: "session=abc",
      host: "evil.test",
      origin: "https://evil.test",
      "user-agent": "node-test",
      "x-forwarded-host": "evil.test",
    })
  );

  assert.equal(copied.get("accept"), "application/json");
  assert.equal(copied.get("content-type"), "application/json");
  assert.equal(copied.get("cookie"), "session=abc");
  assert.equal(copied.get("user-agent"), "node-test");
  assert.equal(copied.get("authorization"), null);
  assert.equal(copied.get("connection"), null);
  assert.equal(copied.get("host"), null);
  assert.equal(copied.get("origin"), null);
  assert.equal(copied.get("x-forwarded-host"), null);
});

test("copyAllowedResponseHeaders preserves response headers needed by app flows", () => {
  const copied = proxyPolicy.copyAllowedResponseHeaders(
    new Headers({
      "cache-control": "no-store",
      connection: "keep-alive",
      "content-disposition": "attachment; filename=export.csv",
      "content-type": "text/csv",
      "set-cookie": "session=abc; Path=/; HttpOnly",
      server: "internal-api",
      "x-debug": "secret",
    })
  );

  assert.equal(copied.get("cache-control"), "no-store");
  assert.equal(copied.get("content-disposition"), "attachment; filename=export.csv");
  assert.equal(copied.get("content-type"), "text/csv");
  assert.equal(copied.get("set-cookie"), "session=abc; Path=/; HttpOnly");
  assert.equal(copied.get("connection"), null);
  assert.equal(copied.get("server"), null);
  assert.equal(copied.get("x-debug"), null);
});

test("isCrossOriginMutation rejects cross-origin mutating requests", () => {
  assert.equal(
    proxyPolicy.isCrossOriginMutation("GET", "https://app.example", "https://evil.example", null),
    false
  );
  assert.equal(
    proxyPolicy.isCrossOriginMutation("POST", "https://app.example", "https://app.example", null),
    false
  );
  assert.equal(
    proxyPolicy.isCrossOriginMutation("POST", "https://app.example", null, "https://app.example/app"),
    false
  );
  assert.equal(
    proxyPolicy.isCrossOriginMutation("POST", "https://app.example", "https://evil.example", null),
    true
  );
  assert.equal(
    proxyPolicy.isCrossOriginMutation("DELETE", "https://app.example", null, "https://evil.example/form"),
    true
  );
  assert.equal(
    proxyPolicy.isCrossOriginMutation("PATCH", "https://app.example", "not a url", null),
    true
  );
});

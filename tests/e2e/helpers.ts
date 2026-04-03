import { execFileSync } from "node:child_process";
import path from "node:path";
import { expect, type Page } from "@playwright/test";

const repoRoot = path.resolve(__dirname, "../..");

export type E2ESeedManifest = {
  admin_email: string;
  member_email: string;
  password: string;
  household_external_id: string;
  household_name: string;
  primary_location_external_id: string;
  primary_location_name: string;
  pantry_group_external_id: string;
  pantry_group_name: string;
  product_external_ids: Record<string, string>;
};

function runRepoScript(scriptPath: string): string {
  return execFileSync("bash", ["-lc", scriptPath], {
    cwd: repoRoot,
    encoding: "utf-8"
  }).trim();
}

export function reseedE2E(): E2ESeedManifest {
  const output = runRepoScript("./infra/scripts/e2e-seed.sh");
  return JSON.parse(output) as E2ESeedManifest;
}

export function runWorkerOnce(): void {
  runRepoScript("./infra/scripts/worker-once.sh");
}

export async function login(
  page: Page,
  credentials: { email: string; password: string }
): Promise<void> {
  await page.goto("/login");
  await expect(page.getByTestId("login-form")).toBeVisible();
  await page.waitForLoadState("networkidle");
  await page.getByLabel("Email").fill(credentials.email);
  await page.getByLabel("Password").fill(credentials.password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/app(?:$|\/)/);
}

export async function loginThroughApi(
  page: Page,
  credentials: { email: string; password: string }
): Promise<void> {
  const response = await page.request.post("http://localhost:8000/api/auth/login", {
    data: credentials
  });
  expect(response.ok()).toBeTruthy();
}

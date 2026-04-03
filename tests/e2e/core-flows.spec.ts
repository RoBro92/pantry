import path from "node:path";
import { expect, test } from "@playwright/test";
import {
  login,
  loginThroughApi,
  reseedE2E,
  runWorkerOnce,
  type E2ESeedManifest
} from "./helpers";

let manifest: E2ESeedManifest;

test.beforeEach(() => {
  manifest = reseedE2E();
});

test("login lands on the authenticated dashboard", async ({ page }) => {
  await login(page, {
    email: manifest.member_email,
    password: manifest.password
  });

  await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();
  await expect(page.locator(".household-card").first().getByText(manifest.household_name)).toBeVisible();
});

test("platform admin diagnostics page loads against the docker stack", async ({ page }) => {
  await loginThroughApi(page, {
    email: manifest.admin_email,
    password: manifest.password
  });

  await page.goto("/admin/diagnostics");

  await expect(page.getByRole("heading", { name: "Measured Runtime State" })).toBeVisible();
  await expect(page.getByText("Deployment mode self_hosted")).toBeVisible();
  await expect(page.getByText("Queue And Worker")).toBeVisible();
});

test("pantry flow covers create location, add stock, move stock, and remove stock", async ({
  page
}) => {
  await loginThroughApi(page, {
    email: manifest.member_email,
    password: manifest.password
  });

  await page.goto(`/app/households/${manifest.household_external_id}`);

  const createLocationForm = page.getByTestId("create-location-form");
  await createLocationForm.locator("select").selectOption({ label: manifest.pantry_group_name });
  await createLocationForm.locator('input[name="name"]').fill("Freezer");
  await createLocationForm.getByRole("button", { name: "Add location" }).click();

  await expect(page.getByRole("heading", { name: "Kitchen / Freezer" })).toBeVisible();

  const addStockForm = page.getByTestId("add-stock-form");
  await addStockForm.locator('select[name="product_external_id"]').selectOption({ label: "Pasta" });
  await addStockForm
    .locator('select[name="location_external_id"]')
    .selectOption({ label: "Kitchen / Shelf A" });
  await addStockForm.locator('input[name="quantity"]').fill("2");
  await addStockForm.locator('input[name="note"]').fill("E2E pantry lot");
  await addStockForm.getByRole("button", { name: "Add stock" }).click();

  const shelfRow = page
    .locator("tbody tr", {
      has: page.locator("td:nth-child(1)", { hasText: "Pasta" })
    })
    .filter({
      has: page.locator("td:nth-child(2)", { hasText: "Kitchen / Shelf A" })
    })
    .filter({
      has: page.locator("td:nth-child(5)", { hasText: "E2E pantry lot" })
    });
  await expect(shelfRow).toContainText("2.000 count");

  const moveForm = shelfRow.locator('form[data-testid^="move-lot-form-"]');
  await moveForm.getByPlaceholder("Qty").fill("1");
  await moveForm.getByRole("combobox").selectOption({ label: "Kitchen / Freezer" });
  await moveForm.getByRole("button", { name: "Move" }).click();

  const freezerRow = page
    .locator("tbody tr", {
      has: page.locator("td:nth-child(1)", { hasText: "Pasta" })
    })
    .filter({
      has: page.locator("td:nth-child(2)", { hasText: "Kitchen / Freezer" })
    })
    .filter({
      has: page.locator("td:nth-child(5)", { hasText: "E2E pantry lot" })
    });
  await expect(freezerRow).toContainText("1.000 count");

  const removeForm = freezerRow.locator('form[data-testid^="remove-lot-form-"]');
  await removeForm.getByPlaceholder("Qty").fill("0.500");
  await removeForm.getByRole("button", { name: "Remove" }).click();

  await expect(freezerRow).toContainText("0.500 count");
});

test("recipe flow covers create, detail view, and pantry coverage display", async ({ page }) => {
  await loginThroughApi(page, {
    email: manifest.member_email,
    password: manifest.password
  });

  await page.goto(`/app/households/${manifest.household_external_id}/recipes/new`);

  const form = page.getByTestId("recipe-form-create");
  await form.getByLabel("Title").fill("Weeknight Pasta");
  await form.getByLabel("Notes").fill("Simple pantry check.");
  await form.getByRole("button", { name: "Add ingredient" }).click();

  const ingredientCards = form.locator(".recipe-ingredient-card");
  await expect(ingredientCards).toHaveCount(2);

  await ingredientCards.nth(0).getByLabel("Name", { exact: true }).fill("Pasta");
  await ingredientCards.nth(0).getByLabel("Quantity", { exact: true }).fill("1");
  await ingredientCards.nth(0).getByLabel("Unit", { exact: true }).fill("count");
  await ingredientCards.nth(0).locator("select").selectOption({ label: "Pasta (count)" });

  await ingredientCards.nth(1).getByLabel("Name", { exact: true }).fill("Tomatoes");
  await ingredientCards.nth(1).getByLabel("Quantity", { exact: true }).fill("1");
  await ingredientCards.nth(1).getByLabel("Unit", { exact: true }).fill("can");
  await ingredientCards.nth(1).locator("select").selectOption({ label: "Tomatoes (can)" });

  await form.getByRole("button", { name: "Create recipe" }).click();

  await expect(page.getByRole("heading", { name: "Weeknight Pasta" })).toBeVisible();
  await expect(page.getByText("Partially covered")).toBeVisible();
  await expect(page.getByText("Tomatoes · 1.000 can")).toBeVisible();
});

test("import flow covers upload, review lines, and confirm into pantry", async ({ page }) => {
  await loginThroughApi(page, {
    email: manifest.member_email,
    password: manifest.password
  });

  await page.goto(`/app/households/${manifest.household_external_id}/imports`);

  const uploadForm = page.getByTestId("import-upload-form");
  await uploadForm.getByLabel("Import source").selectOption({ label: "Online order" });
  await uploadForm.getByLabel("Occurred on").fill("2026-04-01");
  await uploadForm
    .getByLabel("Upload file")
    .setInputFiles(path.resolve("tests/e2e/fixtures/weekly-order.json"));
  await uploadForm.getByLabel("Note").fill("Weekly order");
  await uploadForm.getByRole("button", { name: "Create import" }).click();

  await expect(page.getByRole("heading", { name: "weekly-order.json" })).toBeVisible();

  runWorkerOnce();
  await page.reload();

  await expect(page.getByText("Line 1: Dry pasta")).toBeVisible();
  await expect(page.getByText("Line 3: House Blend")).toBeVisible();

  const unresolvedLine = page
    .locator('[data-testid^="import-line-"]')
    .filter({ hasText: "House Blend" });
  await unresolvedLine.getByLabel("Match product").selectOption({ label: "Spice Blend (jar)" });
  await unresolvedLine.getByLabel("Status").selectOption("matched");
  await unresolvedLine.getByRole("button", { name: "Save line" }).click();

  await expect(page.getByRole("button", { name: "Confirm import" })).toBeEnabled();
  await page.getByRole("button", { name: "Confirm import" }).click();

  await expect(page.getByText(/online_order · status confirmed · created/i)).toBeVisible();

  await page.goto(`/app/households/${manifest.household_external_id}`);
  await expect(page.getByRole("heading", { name: "Spice Blend" })).toBeVisible();
  await expect(page.getByText("3.000 can across 1 lot")).toBeVisible();
});

test("ai flow covers unconfigured and configured-but-unavailable states", async ({ page }) => {
  await loginThroughApi(page, {
    email: manifest.member_email,
    password: manifest.password
  });

  await page.goto(`/app/households/${manifest.household_external_id}/ai`);
  await expect(
    page.getByText("No AI provider is configured for this installation.")
  ).toBeVisible();

  await page.getByRole("button", { name: "Logout" }).click();
  await loginThroughApi(page, {
    email: manifest.admin_email,
    password: manifest.password
  });

  await page.goto("/admin/ai");
  await page.getByLabel("Base URL").fill("http://api:9");
  await page.getByLabel("Default model").fill("llama3.2");
  await page.getByRole("button", { name: "Save configuration" }).click();
  await expect(page.getByText("Provider configuration saved.")).toBeVisible();

  await page.getByRole("button", { name: "Run health check" }).click();
  await expect(page.getByText("Health check failed.")).toBeVisible();

  await page.getByRole("button", { name: "Logout" }).click();
  await loginThroughApi(page, {
    email: manifest.member_email,
    password: manifest.password
  });

  await page.goto(`/app/households/${manifest.household_external_id}/ai`);
  await expect(page.getByText("The configured AI provider is unhealthy.")).toBeVisible();
});

test("location route redirects to login and lands on the correct location page after auth", async ({
  page
}) => {
  await loginThroughApi(page, {
    email: manifest.member_email,
    password: manifest.password
  });

  await page.goto(`/app/households/${manifest.household_external_id}`);

  const locationLink = page
    .locator('[data-testid^="location-link-card-"]')
    .getByRole("link", { name: "Open link" })
    .first();
  const href = await locationLink.getAttribute("href");
  expect(href).not.toBeNull();

  await page.context().clearCookies();
  await page.goto(href!);

  await expect(page).toHaveURL(/\/login\?next=%2Flocations%2F/);
  await expect(page.getByRole("heading", { name: "Pantry Login" })).toBeVisible();

  await page.getByLabel("Email").fill(manifest.member_email);
  await page.getByLabel("Password").fill(manifest.password);
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect(page).toHaveURL(/\/locations\//);
  await expect(page.getByRole("heading", { name: "Kitchen / Shelf A" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Open filtered pantry" })).toBeVisible();
});

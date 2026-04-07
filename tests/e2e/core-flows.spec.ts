import path from "node:path";
import { expect, test } from "@playwright/test";
import {
  login,
  loginThroughApi,
  reseedE2E,
  resetToUninitialized,
  runWorkerOnce,
  type E2ESeedManifest
} from "./helpers";

let manifest: E2ESeedManifest;

test.beforeEach(() => {
  manifest = reseedE2E();
});

test("first-run setup handles staged users, skips optional steps, and completes cleanly", async ({
  page
}) => {
  resetToUninitialized();

  await page.goto("/");
  await expect(page).toHaveURL(/\/setup$/);
  await page.goto("/login");
  await expect(page).toHaveURL(/\/setup$/);

  const wizard = page.getByTestId("setup-wizard");
  const progressItems = wizard.locator(".setup-progress-item");

  await expect(progressItems.nth(0).locator(".setup-progress-count")).toHaveText("1");
  await expect(progressItems.nth(1).locator(".setup-progress-count")).toHaveText("2");

  await wizard.getByRole("button", { name: "Next" }).click();
  const usersStep = page.getByTestId("setup-users-step");
  await expect(page.getByRole("heading", { name: "Admin account and initial users" })).toBeVisible();
  await expect(progressItems.nth(0).locator(".setup-progress-count")).toHaveText("✓");
  await expect(progressItems.nth(1).locator(".setup-progress-count")).toHaveText("2");
  await expect(wizard.getByRole("button", { name: "Next" })).toBeDisabled();
  await expect(page.getByTestId("setup-admin-password-status")).toContainText(
    "Enter a username or email for the platform admin.",
  );

  const adminFields = usersStep.locator(".setup-subsection").nth(0);
  await adminFields.getByLabel("Username or email").fill("owner");
  await expect(page.getByTestId("setup-admin-password-status")).toContainText(
    "Add a password of at least 8 characters before continuing.",
  );

  await adminFields.getByLabel("Display name").fill("Owner");
  await adminFields.getByLabel("Password", { exact: true }).fill("short");
  await adminFields.getByLabel("Confirm password").fill("short");
  await expect(page.getByTestId("setup-admin-password-status")).toContainText(
    "Passwords must be at least 8 characters.",
  );
  await expect(wizard.getByRole("button", { name: "Next" })).toBeDisabled();
  await adminFields.getByLabel("Password", { exact: true }).fill("correct horse battery");
  await adminFields.getByLabel("Confirm password").fill("correct horse battery");
  await page.getByRole("heading", { name: "Admin account and initial users" }).click();
  await expect(page.getByTestId("setup-admin-password-status")).toContainText("Password saved");
  await expect(adminFields.getByLabel("Password", { exact: true })).toHaveValue(
    "correct horse battery",
  );
  await expect(adminFields.getByLabel("Confirm password")).toHaveValue("correct horse battery");

  await usersStep.getByRole("button", { name: "Add additional user" }).click();
  await usersStep.getByRole("button", { name: "Add additional user" }).click();
  await expect(page.getByTestId("setup-user-card-1")).toBeVisible();
  await expect(page.getByTestId("setup-user-card-2")).toBeVisible();

  const firstAdditionalUser = page.getByTestId("setup-user-card-1");
  await firstAdditionalUser.getByLabel("Username or email").fill("alex");
  await firstAdditionalUser.getByLabel("Display name").fill("Alex");
  await firstAdditionalUser.getByLabel("Password", { exact: true }).fill("correct horse battery");
  await firstAdditionalUser
    .getByLabel("Confirm password")
    .fill("correct horse battery");

  const secondAdditionalUser = page.getByTestId("setup-user-card-2");
  await secondAdditionalUser.getByLabel("Username or email").fill("bea");
  await secondAdditionalUser.getByLabel("Display name").fill("Bea");
  await secondAdditionalUser.getByRole("button", { name: "Remove" }).click();
  await expect(page.getByTestId("setup-user-card-2")).toHaveCount(0);

  await page.getByRole("heading", { name: "Admin account and initial users" }).click();
  await expect(page.getByText("Users saved.")).toBeVisible();
  await expect(wizard.getByRole("button", { name: "Next" })).toBeEnabled();

  await page.reload();
  await expect(page.getByRole("heading", { name: "Admin account and initial users" })).toBeVisible();
  await expect(progressItems.nth(0).locator(".setup-progress-count")).toHaveText("✓");
  await expect(progressItems.nth(1).locator(".setup-progress-count")).toHaveText("2");
  await expect(progressItems.nth(2).locator(".setup-progress-count")).toHaveText("3");
  await expect(page.getByTestId("setup-user-card-1").getByLabel("Username or email")).toHaveValue("alex");
  await expect(page.getByTestId("setup-user-card-1").getByLabel("Display name")).toHaveValue("Alex");
  await expect(page.getByTestId("setup-user-card-2")).toHaveCount(0);

  await wizard.getByRole("button", { name: "Next" }).click();
  await expect(page.getByRole("heading", { name: "Household and storage locations" })).toBeVisible();

  await page.getByLabel("Household name").fill("Brown Household");
  await page.getByLabel("Default storage location").fill("Kitchen");
  await page.getByLabel("Additional storage locations").fill("Fridge");
  await page.getByRole("button", { name: "Add" }).first().click();
  await page
    .getByLabel("Household membership for Alex (alex)")
    .selectOption({ label: "User" });
  await expect(page.getByText("Household details saved.")).toBeVisible();
  await expect(page.getByLabel(/Household membership for .*owner/i)).toBeDisabled();
  await expect(page.getByLabel(/Household membership for .*owner/i)).toHaveValue(
    "household_admin",
  );
  await expect(page.getByLabel("Household membership for Alex (alex)")).toHaveValue(
    "household_user",
  );

  await page.reload();
  await expect(page.getByRole("heading", { name: "Household and storage locations" })).toBeVisible();
  await expect(page.getByLabel("Household name")).toHaveValue("Brown Household");
  await expect(page.getByRole("button", { name: "Fridge Remove" })).toBeVisible();
  await expect(page.getByLabel("Household membership for Alex (alex)")).toHaveValue(
    "household_user",
  );

  await wizard.getByRole("button", { name: "Next" }).click();
  await expect(page.getByRole("heading", { name: "Public browser URL" })).toBeVisible();
  await expect(wizard.getByRole("button", { name: "Skip for now" })).toBeVisible();
  await wizard.getByRole("button", { name: "Skip for now" }).click();

  await expect(page.getByRole("heading", { name: "Dietary preferences" })).toBeVisible();
  await wizard.getByRole("button", { name: "Skip for now" }).click();
  await expect(page.getByRole("heading", { name: "AI configuration" })).toBeVisible();
  await wizard.getByRole("button", { name: "Skip for now" }).click();
  await expect(page.getByRole("heading", { name: "SMTP configuration" })).toBeVisible();
  await wizard.getByRole("button", { name: "Skip for now" }).click();

  await expect(page.getByRole("heading", { name: "Review and complete" })).toBeVisible();
  await expect(progressItems.nth(2).locator(".setup-progress-count")).toHaveText("✓");
  await expect(progressItems.nth(3).locator(".setup-progress-count")).toHaveText("✓");
  await expect(progressItems.nth(4).locator(".setup-progress-count")).toHaveText("✓");
  await expect(progressItems.nth(5).locator(".setup-progress-count")).toHaveText("✓");
  await expect(progressItems.nth(6).locator(".setup-progress-count")).toHaveText("✓");
  await expect(page.getByText("Skipped for now")).toHaveCount(4);
  await expect(page.getByText(/Alex \(alex\) \(User\)/)).toBeVisible();
  await wizard.getByRole("button", { name: "Complete Setup" }).click();

  await expect(page).toHaveURL(/\/app$/);
  await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();
  await expect(page.locator(".household-card").getByText("Brown Household")).toBeVisible();
});

test("setup can restore from a staged Pantry backup bundle", async ({ page }) => {
  await loginThroughApi(page, {
    email: manifest.admin_email,
    password: manifest.password
  });

  const exportResponse = await page.request.get(
    "http://localhost:8000/api/platform-admin/backups/export/instance"
  );
  expect(exportResponse.ok()).toBeTruthy();
  const backupText = await exportResponse.text();

  resetToUninitialized();
  await page.context().clearCookies();

  await page.goto("/setup");
  const wizard = page.getByTestId("setup-wizard");
  await wizard.getByRole("button", { name: "Next" }).click();

  await expect(page.getByRole("heading", { name: "Fresh install or restore from backup" })).toBeVisible();
  await page.getByRole("button", { name: "Choose restore" }).click();
  await expect(page.getByText("Restore mode selected.")).toBeVisible();

  await page.locator('input[type="file"][name="file"]').setInputFiles({
    name: "pantry-instance-backup.json",
    mimeType: "application/json",
    buffer: Buffer.from(backupText, "utf-8")
  });
  await page.getByRole("button", { name: "Upload and validate" }).click();

  await expect(page.getByText("Restore backup staged safely.")).toBeVisible();
  await expect(page.getByText("Staged restore bundle")).toBeVisible();
  await expect(
    page.getByText("Restore currently supports full instance Pantry backup bundles only.")
  ).toBeVisible();

  await wizard.getByRole("button", { name: "Next" }).click();
  await expect(page.getByRole("heading", { name: "Review and complete" })).toBeVisible();

  const finalizeResponse = await page.request.post("http://localhost:8000/api/setup/wizard/finalize", {
    data: {}
  });
  expect(finalizeResponse.ok()).toBeTruthy();

  await page.goto("/app");
  await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();
  await expect(page.getByText("Logged in as E2E Admin")).toBeVisible();

  await page.goto("/admin/households");
  await expect(page.getByRole("cell", { name: manifest.household_name })).toBeVisible();
});

test("dietary none selection persists and marks the step complete", async ({ page }) => {
  resetToUninitialized();

  await page.goto("/setup");
  const wizard = page.getByTestId("setup-wizard");
  await wizard.getByRole("button", { name: "Next" }).click();

  const usersStep = page.getByTestId("setup-users-step");
  await usersStep.getByLabel("Username or email").fill("owner");
  await usersStep.getByLabel("Password", { exact: true }).fill("correct horse battery");
  await usersStep.getByLabel("Confirm password").fill("correct horse battery");
  await wizard.getByRole("button", { name: "Next" }).click();

  await page.getByLabel("Household name").fill("Brown Household");
  await page.getByLabel("Additional storage locations").fill("Fridge");
  await page.getByRole("button", { name: "Add" }).first().click();
  await wizard.getByRole("button", { name: "Next" }).click();
  await wizard.getByRole("button", { name: "Skip for now" }).click();

  await expect(page.getByRole("heading", { name: "Dietary preferences" })).toBeVisible();
  await page.getByRole("button", { name: "None" }).first().click();
  await expect(page.getByRole("button", { name: "None Remove" })).toBeVisible();

  await page.reload();
  await expect(page.getByRole("heading", { name: "Dietary preferences" })).toBeVisible();
  await expect(page.getByRole("button", { name: "None Remove" })).toBeVisible();

  await wizard.getByRole("button", { name: "Next" }).click();
  await expect(page.getByRole("heading", { name: "AI configuration" })).toBeVisible();
  await expect(wizard.locator(".setup-progress-item").nth(4).locator(".setup-progress-count")).toHaveText(
    "✓",
  );
});

test("setup and login forms render explicit autofill-safe field metadata", async ({ page }) => {
  resetToUninitialized();

  await page.goto("/setup");
  const wizard = page.getByTestId("setup-wizard");
  await wizard.getByRole("button", { name: "Next" }).click();

  const usersStep = page.getByTestId("setup-users-step");
  const adminLogin = usersStep.locator('input[name="setup_admin_login"]');
  await expect(adminLogin).toHaveAttribute("type", "text");
  await expect(adminLogin).toHaveAttribute("autocomplete", "section-setup-admin username");
  await expect(adminLogin).toHaveAttribute("autocapitalize", "none");
  await expect(adminLogin).toHaveAttribute("autocorrect", "off");

  const adminPassword = usersStep.locator('input[name="setup_admin_password"]');
  await expect(adminPassword).toHaveAttribute("type", "password");
  await expect(adminPassword).toHaveAttribute(
    "autocomplete",
    "section-setup-admin new-password",
  );

  await usersStep.getByRole("button", { name: "Add additional user" }).click();
  await expect(usersStep.locator('input[name^="setup_user_"][name$="_login"]').first()).toHaveAttribute(
    "autocomplete",
    /section-setup-user-.* username/,
  );
  await expect(
    usersStep.locator('input[name^="setup_user_"][name$="_password"]').first(),
  ).toHaveAttribute("autocomplete", /section-setup-user-.* new-password/);

  await wizard.getByRole("button", { name: "Public URL Optional" }).click();
  const publicUrl = page.locator('input[name="setup_public_base_url"]');
  await expect(publicUrl).toHaveAttribute("type", "url");
  await expect(publicUrl).toHaveAttribute("autocomplete", "url");
  await expect(publicUrl).toHaveAttribute("inputmode", "url");

  reseedE2E();
  await page.goto("/login");
  const loginForm = page.getByTestId("login-form");
  await expect(loginForm.locator('input[name="identifier"]')).toHaveAttribute(
    "autocomplete",
    "section-login username",
  );
  await expect(loginForm.locator('input[name="password"]')).toHaveAttribute(
    "autocomplete",
    "section-login current-password",
  );
});

test("completed installs use the login page as the default entry point", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();
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

  await expect(page.getByRole("heading", { name: "Runtime State" })).toBeVisible();
  await expect(page.getByText(/Deployment Self-hosted/i)).toBeVisible();
  await expect(page.getByText(/uptime .*minute/i)).toBeVisible();
  await expect(page.getByText("Update Check")).toBeVisible();
  await expect(page.getByText("Queue And Worker")).toBeVisible();
  await expect(page.getByText("Default")).toBeVisible();
});

test("platform admin updates and backups pages load from the admin navigation", async ({
  page
}) => {
  await loginThroughApi(page, {
    email: manifest.admin_email,
    password: manifest.password
  });

  await page.goto("/admin/updates");
  await expect(page.getByRole("heading", { name: "Release visibility and manual updates" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Backups", exact: true })).toBeVisible();
  await expect(page.getByText("Operator-controlled only")).toBeVisible();

  await page.goto("/admin/backups");
  await expect(page.getByRole("heading", { name: "Export and recovery foundations" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Updates", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Download full backup" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Upload and validate" })).toBeVisible();
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

test("platform admin can create a user, create a household, and assign membership", async ({
  page
}) => {
  await loginThroughApi(page, {
    email: manifest.admin_email,
    password: manifest.password
  });

  await page.goto("/admin/users");

  const createUserForm = page.getByTestId("admin-create-user-form");
  await createUserForm.getByLabel("Email").fill("weekday-member@example.com");
  await createUserForm.getByLabel("Display name").fill("Weekday Member");
  await createUserForm.getByLabel("Password", { exact: true }).fill(manifest.password);
  await createUserForm.getByLabel("Confirm password").fill(manifest.password);
  await createUserForm.getByRole("button", { name: "Create user" }).click();

  await expect(page.getByRole("cell", { name: "weekday-member@example.com" })).toBeVisible();

  await page.goto("/admin/households");

  const createHouseholdForm = page.getByTestId("admin-create-household-form");
  await createHouseholdForm.getByLabel("Household name").fill("Weekday Household");
  await createHouseholdForm.getByRole("button", { name: "Create household" }).click();

  await expect(page.getByRole("cell", { name: "Weekday Household" })).toBeVisible();

  const membershipForm = page.getByTestId("admin-assign-membership-form");
  await membershipForm
    .locator('select[name="household_external_id"]')
    .selectOption({ label: "Weekday Household" });
  await membershipForm
    .locator('select[name="user_external_id"]')
    .selectOption({ label: "Weekday Member (weekday-member@example.com)" });
  await membershipForm.locator('select[name="role"]').selectOption({ label: "User" });
  await membershipForm.getByRole("button", { name: "Assign membership" }).click();

  await expect(page.getByText("Assigned weekday-member@example.com as User.")).toBeVisible();
  await expect(page.getByRole("row", { name: /Weekday Household .*Weekday Member \(User\)/ })).toBeVisible();

  await page.getByRole("button", { name: "Logout" }).click();

  await login(page, {
    email: "weekday-member@example.com",
    password: manifest.password
  });

  await expect(page.locator(".household-card").getByText("Weekday Household")).toBeVisible();
  await page
    .locator(".household-card", { hasText: "Weekday Household" })
    .getByRole("link", { name: "Open pantry" })
    .click();

  await expect(page.getByRole("heading", { name: "Weekday Household" })).toBeVisible();
  await expect(page.getByText("Household-admin actions only")).toBeVisible();
});

test("platform admin can remove household members and delete a household with confirmation", async ({
  page
}) => {
  await loginThroughApi(page, {
    email: manifest.admin_email,
    password: manifest.password
  });

  await page.goto("/admin/users");

  const createUserForm = page.getByTestId("admin-create-user-form");
  await createUserForm.getByLabel("Email").fill("cleanup-member@example.com");
  await createUserForm.getByLabel("Display name").fill("Cleanup Member");
  await createUserForm.getByLabel("Password", { exact: true }).fill(manifest.password);
  await createUserForm.getByLabel("Confirm password").fill(manifest.password);
  await createUserForm.getByRole("button", { name: "Create user" }).click();

  await page.goto("/admin/households");

  const createHouseholdForm = page.getByTestId("admin-create-household-form");
  await createHouseholdForm.getByLabel("Household name").fill("Cleanup Household");
  await createHouseholdForm.getByRole("button", { name: "Create household" }).click();
  await expect(page.getByRole("cell", { name: "Cleanup Household" })).toBeVisible();

  const membershipForm = page.getByTestId("admin-assign-membership-form");
  await membershipForm
    .locator('select[name="household_external_id"]')
    .selectOption({ label: "Cleanup Household" });
  await membershipForm
    .locator('select[name="user_external_id"]')
    .selectOption({ label: "Cleanup Member (cleanup-member@example.com)" });
  await membershipForm.locator('select[name="role"]').selectOption({ label: "User" });
  await membershipForm.getByRole("button", { name: "Assign membership" }).click();
  await expect(page.getByText("Assigned cleanup-member@example.com as User.")).toBeVisible();

  const maintenanceForm = page.getByTestId("admin-household-maintenance-form");
  await maintenanceForm
    .locator('select[name="maintenance_household_external_id"]')
    .selectOption({ label: "Cleanup Household" });

  page.once("dialog", async (dialog) => {
    expect(dialog.message()).toContain("Remove Cleanup Member");
    await dialog.accept();
  });
  await maintenanceForm
    .locator(".table-member-row", { hasText: "cleanup-member@example.com" })
    .getByRole("button", { name: "Remove" })
    .click();

  await expect(page.getByText("Household membership removed.")).toBeVisible();
  await expect(
    maintenanceForm.locator(".table-member-row", { hasText: "cleanup-member@example.com" })
  ).toHaveCount(0);

  await maintenanceForm.getByLabel("Type the household name to confirm deletion").fill("Cleanup Household");
  await maintenanceForm.getByRole("button", { name: "Delete household" }).click();

  await expect(page.getByText("Household deleted.")).toBeVisible();
  await expect(page.getByRole("cell", { name: "Cleanup Household" })).toHaveCount(0);
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
  await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();

  await page.getByLabel("Username or email").fill(manifest.member_email);
  await page.getByLabel("Password").fill(manifest.password);
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect(page).toHaveURL(/\/locations\//);
  await expect(page.getByRole("heading", { name: "Kitchen / Shelf A" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Open filtered pantry" })).toBeVisible();
});

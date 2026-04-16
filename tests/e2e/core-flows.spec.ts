import path from "node:path";
import { expect, test, type Page } from "@playwright/test";
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

test("web-origin API proxy forwards health, setup, login, and session requests", async ({
  page
}) => {
  resetToUninitialized();

  const healthResponse = await page.request.get("/api/health");
  expect(healthResponse.ok()).toBeTruthy();
  expect(await healthResponse.json()).toMatchObject({ status: "ok" });

  const setupStatusResponse = await page.request.get("/api/setup/status");
  expect(setupStatusResponse.ok()).toBeTruthy();
  expect(await setupStatusResponse.json()).toMatchObject({ is_initialized: false });

  manifest = reseedE2E();
  await page.context().clearCookies();

  const loginResponse = await page.request.post("/api/auth/login", {
    data: {
      identifier: manifest.admin_email,
      password: manifest.password
    }
  });
  expect(loginResponse.ok()).toBeTruthy();

  const sessionResponse = await page.request.get("/api/auth/session");
  expect(sessionResponse.ok()).toBeTruthy();
  expect(await sessionResponse.json()).toMatchObject({
    user: {
      email: manifest.admin_email
    }
  });
});

async function dismissAdminWhatsNewIfVisible(page: Page) {
  const response = await page.request.post(
    "http://localhost:8000/api/platform-admin/release-status/mark-seen",
    {
      data: {}
    }
  );
  expect(response.ok()).toBeTruthy();
}

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

  await expect(page.getByRole("heading", { name: "Install selection" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Selected" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Choose restore" })).toBeVisible();
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
  await expect(page.getByTestId("setup-user-card-1")).toBeVisible();
  await usersStep.getByRole("button", { name: "Add additional user" }).click();
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
  await expect(page.getByRole("heading", { name: "Dietary preferences" })).toBeVisible();
  await wizard.getByRole("button", { name: "Skip for now" }).click();
  await expect(page.getByRole("heading", { name: "Create household and rooms" })).toBeVisible();

  await page.getByLabel("Household name").fill("Brown Household");
  const firstRoomCard = page.getByTestId("setup-room-card-1");
  await firstRoomCard.getByLabel("Room name").fill("Kitchen");
  await firstRoomCard.getByLabel("Storage locations").fill("Fridge");
  const firstRoomSave = page.waitForResponse(
    (response) =>
      response.url().includes("/api/setup/wizard/household") &&
      response.request().method() === "PUT" &&
      response.request().postData()?.includes('"Fridge"') === true &&
      response.ok(),
  );
  await firstRoomCard.getByRole("button", { name: "Add" }).click();
  await firstRoomSave;
  await expect(firstRoomCard.getByRole("button", { name: "Fridge Remove" })).toBeVisible();
  await wizard.getByRole("button", { name: "Add another Room" }).click();
  const secondRoomCard = page.getByTestId("setup-room-card-2");
  await expect(secondRoomCard).toBeVisible();
  const secondRoomToggle = secondRoomCard.locator(".setup-room-toggle");
  if ((await secondRoomToggle.getAttribute("aria-expanded")) !== "true") {
    await secondRoomToggle.click();
  }
  await expect(secondRoomCard.getByLabel("Room name")).toBeVisible();
  await secondRoomCard.getByLabel("Room name").fill("Garage");
  await secondRoomCard.getByLabel("Storage locations").fill("Bulk rack");
  const secondRoomSave = page.waitForResponse(
    (response) =>
      response.url().includes("/api/setup/wizard/household") &&
      response.request().method() === "PUT" &&
      response.request().postData()?.includes('"Bulk rack"') === true &&
      response.ok(),
  );
  await secondRoomCard.getByRole("button", { name: "Add" }).click();
  await secondRoomSave;
  await expect(secondRoomCard.getByRole("button", { name: "Bulk rack Remove" })).toBeVisible();
  const householdRoleSave = page.waitForResponse(
    (response) =>
      response.url().includes("/api/setup/wizard/household") &&
      response.request().method() === "PUT" &&
      response.request().postData()?.includes('"role":"household_user"') === true &&
      response.ok(),
  );
  await page.getByLabel("Household membership for Alex (alex)").selectOption({ label: "User" });
  await householdRoleSave;
  await expect(page.getByText("Household details saved.")).toBeVisible();
  await expect(page.getByLabel(/Household membership for .*owner/i)).toBeDisabled();
  await expect(page.getByLabel(/Household membership for .*owner/i)).toHaveValue(
    "household_admin",
  );
  await expect(page.getByLabel("Household membership for Alex (alex)")).toHaveValue(
    "household_user",
  );

  await page.reload();
  await expect(page.getByRole("heading", { name: "Create household and rooms" })).toBeVisible();
  await expect(page.getByLabel("Household name")).toHaveValue("Brown Household");
  await expect(page.getByTestId("setup-room-card-1")).toContainText("Kitchen");
  await expect(page.getByTestId("setup-room-card-2")).toContainText("Garage");
  await expect(page.getByRole("button", { name: "Fridge Remove" })).toBeVisible();
  await expect(page.getByLabel("Household membership for Alex (alex)")).toHaveValue(
    "household_user",
  );

  await wizard.getByRole("button", { name: "Next" }).click();
  await expect(page.getByRole("heading", { name: "Public browser URL" })).toBeVisible();
  await expect(wizard.getByRole("button", { name: "Skip for now" })).toBeVisible();
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
  await expect(progressItems.nth(7).locator(".setup-progress-count")).toHaveText("8");
  await expect(page.getByText("Skipped for now").first()).toBeVisible();
  await expect(page.getByText(/Alex \(alex\) \(User\)/)).toBeVisible();
  await expect(page.getByText(/Room 2: Garage/)).toBeVisible();
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
  await expect(page.getByRole("heading", { name: "Install selection" })).toBeVisible();
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

test("setup shows a clear restore error when a backup cannot be restored on this schema", async ({
  page
}) => {
  await loginThroughApi(page, {
    email: manifest.admin_email,
    password: manifest.password
  });

  const exportResponse = await page.request.get(
    "http://localhost:8000/api/platform-admin/backups/export/instance"
  );
  expect(exportResponse.ok()).toBeTruthy();
  const backup = JSON.parse(await exportResponse.text()) as {
    schema_revision: string | null;
  };
  backup.schema_revision = "mismatched-schema-revision";

  resetToUninitialized();
  await page.context().clearCookies();

  await page.goto("/setup");
  const wizard = page.getByTestId("setup-wizard");

  await page.getByRole("button", { name: "Choose restore" }).click();
  await page.locator('input[type="file"][name="file"]').setInputFiles({
    name: "pantry-instance-backup.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify(backup), "utf-8")
  });
  await page.getByRole("button", { name: "Upload and validate" }).click();

  await expect(
    page.getByText("Backup uploaded, but Pantry cannot restore it on this installation.")
  ).toBeVisible();
  await expect(page.getByTestId("setup-restore-blocked")).toContainText(
    "Cross-version restore is not supported yet."
  );
  await expect(page.getByText("Restore blocked for this backup")).toBeVisible();
  await expect(wizard.getByRole("button", { name: "Next" })).toBeDisabled();
});

test("dietary none selection persists and marks the step complete", async ({ page }) => {
  resetToUninitialized();

  await page.goto("/setup");
  const wizard = page.getByTestId("setup-wizard");

  const usersStep = page.getByTestId("setup-users-step");
  await wizard.getByRole("button", { name: "Next" }).click();
  await usersStep.getByLabel("Username or email").fill("owner");
  await usersStep.getByLabel("Password", { exact: true }).fill("correct horse battery");
  await usersStep.getByLabel("Confirm password").fill("correct horse battery");
  await expect(wizard.locator(".setup-progress-item").nth(2)).toContainText("Dietary preferences");
  await wizard.locator(".setup-progress-item").nth(2).click();
  await expect(page.getByRole("heading", { name: "Dietary preferences" })).toBeVisible();
  await page.getByRole("button", { name: "None" }).first().click();
  await expect(page.getByRole("button", { name: "None Remove" })).toBeVisible();
  await wizard.getByRole("button", { name: "Next" }).click();
  await expect(page.getByRole("heading", { name: "Create household and rooms" })).toBeVisible();
  await expect(
    wizard.locator(".setup-progress-item").nth(2).locator(".setup-progress-count"),
  ).toHaveText("✓");

  await page.reload();
  await wizard.locator(".setup-progress-item").nth(2).click();
  await expect(page.getByRole("heading", { name: "Dietary preferences" })).toBeVisible();
  await expect(page.getByRole("button", { name: "None Remove" })).toBeVisible();
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
  await expect(page.getByText("Environment override")).toBeVisible();
});

test("platform admin updates and backups pages load from the admin navigation", async ({
  page
}) => {
  await loginThroughApi(page, {
    email: manifest.admin_email,
    password: manifest.password
  });

  await page.goto("/admin/updates");
  await expect(page.getByRole("heading", { name: "Releases and manual updates" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Backups", exact: true })).toBeVisible();
  await expect(
    page
      .locator("article.panel")
      .filter({ has: page.getByRole("heading", { name: "Manual Update" }) })
      .getByText(/Operator controlled/i)
  ).toBeVisible();

  await page.goto("/admin/backups");
  await expect(page.getByRole("heading", { name: "Backup and Restore" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Updates", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Download full backup" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Upload and validate" })).toBeVisible();
});

test("authenticated shell stays horizontally stable across admin tabs", async ({ page }) => {
  await loginThroughApi(page, {
    email: manifest.admin_email,
    password: manifest.password
  });
  await dismissAdminWhatsNewIfVisible(page);

  await page.goto("/admin/updates");
  const sidebar = page.locator(".sidebar");
  const shellContent = page.locator(".shell-content");

  const firstSidebarBox = await sidebar.boundingBox();
  const firstContentBox = await shellContent.boundingBox();
  expect(firstSidebarBox).not.toBeNull();
  expect(firstContentBox).not.toBeNull();

  await page.goto("/admin/backups");
  await expect(page.getByRole("heading", { name: "Backup and Restore" })).toBeVisible();

  const secondSidebarBox = await sidebar.boundingBox();
  const secondContentBox = await shellContent.boundingBox();
  expect(secondSidebarBox).not.toBeNull();
  expect(secondContentBox).not.toBeNull();

  expect(Math.abs((firstSidebarBox?.x ?? 0) - (secondSidebarBox?.x ?? 0))).toBeLessThan(1);
  expect(Math.abs((firstContentBox?.x ?? 0) - (secondContentBox?.x ?? 0))).toBeLessThan(1);
});

test("update availability banner is shown only to admins when an update is available", async ({
  page
}) => {
  await loginThroughApi(page, {
    email: manifest.admin_email,
    password: manifest.password
  });

  const releaseStatusResponse = await page.request.get(
    "http://localhost:8000/api/platform-admin/release-status"
  );
  expect(releaseStatusResponse.ok()).toBeTruthy();
  const releaseStatus = await releaseStatusResponse.json();
  test.skip(
    releaseStatus.status !== "update_available",
    "Local stack did not report an update-available state.",
  );

  await page.goto("/admin");
  await expect(page.getByTestId("admin-update-banner")).toBeVisible();
  await expect(page.getByRole("link", { name: "Review update" })).toBeVisible();

  await page.getByRole("button", { name: "Logout" }).click();
  await loginThroughApi(page, {
    email: manifest.member_email,
    password: manifest.password
  });

  await page.goto("/app");
  await expect(page.getByTestId("admin-update-banner")).toHaveCount(0);
});

test("pantry flow covers room management, combined add flow, duplicate handling, and search", async ({
  page
}) => {
  await loginThroughApi(page, {
    email: manifest.member_email,
    password: manifest.password
  });

  await page.goto(`/app/households/${manifest.household_external_id}`);

  await page.getByRole("button", { name: "Manage rooms" }).click();
  const createLocationForm = page.getByTestId("pantry-create-location-form");
  await createLocationForm
    .locator('select[name="location_group_external_id"]')
    .selectOption({ label: manifest.pantry_group_name });
  await createLocationForm.getByLabel("Storage location").fill("Freezer");
  await createLocationForm.getByRole("button", { name: "Add storage location" }).click();
  await expect(createLocationForm.getByText("Saved.")).toBeVisible();
  await page.getByRole("button", { name: "Close" }).click();

  await page.getByRole("button", { name: "Add product" }).click();
  const addEntryForm = page.getByTestId("pantry-add-entry-form");
  await addEntryForm.getByLabel("Product name").fill("Beef mince");
  await addEntryForm.getByLabel("Manual ingredients").fill("Beef");
  await addEntryForm.getByRole("button", { name: "Add", exact: true }).click();
  await addEntryForm.getByLabel("Storage location").selectOption({ label: "Kitchen / Freezer" });
  await addEntryForm.getByLabel("Quantity").fill("2");
  await addEntryForm.getByLabel("Unit").selectOption("kg");
  await addEntryForm.getByLabel("Aliases").fill("Ground beef,mince beef");
  await addEntryForm.getByLabel("Purchase date").fill("2026-04-01");
  await addEntryForm.getByLabel("Expiry date").fill("2026-04-04");
  await addEntryForm.getByLabel("Lot note").fill("First pack");
  await expect(addEntryForm.getByRole("button", { name: "Look up" })).toBeVisible();
  await expect(addEntryForm.getByRole("button", { name: "Scan" })).toBeVisible();
  await addEntryForm.getByRole("button", { name: "Add to pantry" }).click();

  const beefMinceCard = page
    .locator('[data-testid^="product-card-"]')
    .filter({ hasText: "Beef mince" });
  await expect(beefMinceCard).toContainText("2 kg across 1 lot");
  await expect(beefMinceCard).toContainText("Kitchen / Freezer");
  await expect(beefMinceCard).toContainText("4 Apr 2026");
  await expect(beefMinceCard).toContainText("Beef");

  await page.getByLabel("Search products").fill("mince beef");
  await page.getByRole("button", { name: "Apply" }).click();

  await expect(page.getByLabel("Search products")).toHaveValue("mince beef");
  await expect(beefMinceCard).toContainText("Beef mince");

  await page.getByRole("button", { name: "Add product" }).click();
  const duplicateForm = page.getByTestId("pantry-add-entry-form");
  await duplicateForm.getByLabel("Product name").fill("Mince beef");
  await duplicateForm.getByLabel("Storage location").selectOption({ label: "Kitchen / Shelf A" });
  await duplicateForm.getByLabel("Quantity").fill("1");
  await duplicateForm.getByLabel("Unit").selectOption("kg");
  await duplicateForm.getByLabel("Lot note").fill("Second pack");
  await duplicateForm.getByRole("button", { name: "Add to pantry" }).click();

  await expect(page.getByText("Beef mince already looks like the right product")).toBeVisible();
  await duplicateForm.getByRole("button", { name: "Add to pantry" }).click();

  await expect(beefMinceCard).toContainText("3 kg across 2 lots");
  await beefMinceCard.getByRole("button", { name: "Show" }).click();
  await expect(beefMinceCard.locator('[data-testid^="stock-lot-card-"]')).toHaveCount(2);
  await expect(beefMinceCard).toContainText("Second pack");
});

test("pantry add flow warns when an alias is already used by another product", async ({ page }) => {
  await loginThroughApi(page, {
    email: manifest.member_email,
    password: manifest.password
  });

  await page.goto(`/app/households/${manifest.household_external_id}`);
  await page.getByRole("button", { name: "Add product" }).click();

  const addEntryForm = page.getByTestId("pantry-add-entry-form");
  await addEntryForm.getByLabel("Product name").fill("Soup base");
  await addEntryForm.getByLabel("Storage location").selectOption({ label: "Kitchen / Shelf A" });
  await addEntryForm.getByLabel("Quantity").fill("1");
  await addEntryForm.getByLabel("Unit").selectOption("count");
  await addEntryForm.getByLabel("Aliases").fill("Dry pasta");
  await addEntryForm.getByRole("button", { name: "Add to pantry" }).click();

  await expect(page.getByText("Dry pasta is already used by Pasta")).toBeVisible();
});

test("quick add queues repeated scans and saves the reviewed batch into Pantry", async ({
  page
}) => {
  await loginThroughApi(page, {
    email: manifest.member_email,
    password: manifest.password
  });

  await page.goto(`/app/households/${manifest.household_external_id}`);
  await page.getByRole("button", { name: "Quick add" }).click();

  const quickAddDialog = page.getByTestId("pantry-quick-add-dialog");
  await quickAddDialog.getByLabel("Common storage location").selectOption({
    label: "Kitchen / Shelf A"
  });

  const captureField = quickAddDialog.getByLabel("Barcode capture");
  await captureField.fill("00123");
  await captureField.press("Enter");
  await captureField.fill("00123");
  await captureField.press("Enter");
  await captureField.fill("5555555555555");
  await captureField.press("Enter");

  const pastaQuickRow = quickAddDialog
    .locator(".quick-add-item-card")
    .filter({ hasText: "Barcode 00123" });
  await expect(pastaQuickRow).toContainText("2 scans");
  await expect(pastaQuickRow.getByLabel("Product name")).toHaveValue("Pasta");
  await expect(pastaQuickRow).toContainText("Add lot to existing product");

  const oatsQuickRow = quickAddDialog
    .locator(".quick-add-item-card")
    .filter({ hasText: "Barcode 5555555555555" });
  await oatsQuickRow.getByLabel("Product name").fill("Oats");
  await oatsQuickRow.getByLabel("Unit").fill("bag");

  await quickAddDialog.getByRole("button", { name: "Add 2 queued items" }).click();
  await expect(quickAddDialog).toContainText("Added 2 items to Pantry.");
  await page.getByRole("button", { name: "Close" }).click();

  const pastaRow = page
    .locator('[data-testid^="product-card-"]')
    .filter({ hasText: "Pasta" });
  await expect(pastaRow).toContainText("3 count across 1 lot");

  const oatsRow = page
    .locator('[data-testid^="product-card-"]')
    .filter({ hasText: "Oats" });
  await expect(oatsRow).toContainText("1 bag across 1 lot");
  await expect(oatsRow).toContainText("Kitchen / Shelf A");
});

test("shopping reconciliation uses dense rows, full Pantry product creation, and product editing", async ({
  page
}) => {
  await loginThroughApi(page, {
    email: manifest.member_email,
    password: manifest.password
  });

  await page.goto(`/app/households/${manifest.household_external_id}/shopping-list`);

  const addForm = page.locator(".shopping-add-form");
  await addForm.getByLabel("Add item").fill("Olive oil");
  await addForm.getByLabel("Qty").fill("2");
  await addForm.getByLabel("Unit").fill("bottle");
  await addForm.getByLabel("Note").fill("Extra virgin");
  await addForm.getByRole("button", { name: "Add item" }).click();

  await page.getByRole("button", { name: "Export List (.txt)" }).click();
  const pendingTrips = page
    .locator(".content-grid.shopping-columns article.panel")
    .nth(1)
    .locator(".shopping-item-card");
  await expect(pendingTrips.first()).toBeVisible();

  const pendingTrip = pendingTrips.first();
  await pendingTrip.getByRole("button").click();

  await expect(page.locator(".shopping-reconcile-table-heading")).toContainText("Purchased qty");
  const oliveOilRow = page
    .locator('[data-testid^="shopping-reconcile-row-"]')
    .filter({ hasText: "Olive oil" });
  await expect(oliveOilRow).toBeVisible();
  await expect(oliveOilRow.getByLabel("Delete item")).toBeVisible();
  await expect(oliveOilRow.getByLabel("Return item to shopping list")).toBeVisible();
  await expect(oliveOilRow.getByLabel("Reconcile item")).toBeVisible();

  await oliveOilRow.getByLabel("Expand details").click();
  await expect(oliveOilRow).toContainText("Requested");
  await oliveOilRow.getByRole("button", { name: "Create Pantry product" }).click();

  const productForm = page.getByTestId("pantry-product-form");
  const barcodeInput = productForm.locator('input[name="barcodes"]');
  await expect(barcodeInput).toBeVisible();
  await expect(productForm.getByLabel("Aliases")).toBeVisible();
  await expect(productForm.getByLabel("Product notes")).toBeVisible();
  await barcodeInput.fill("5060000000001");
  await productForm.getByLabel("Aliases").fill("EVOO, extra virgin oil");
  await productForm.getByLabel("Product notes").fill("Use for dressings and low-heat cooking.");
  await productForm.getByLabel("Manual ingredients").fill("Olives");
  await productForm.getByRole("button", { name: "Add" }).click();
  await productForm.getByRole("button", { name: "Create product" }).click();

  const refreshedOliveOilRow = page
    .locator('[data-testid^="shopping-reconcile-row-"]')
    .filter({ hasText: "Olive oil" });
  await expect(refreshedOliveOilRow).toContainText("Pantry product");
  await page.goto(`/app/households/${manifest.household_external_id}/shopping-list/history`);
  await expect(page.getByRole("heading", { name: "Shopping history" })).toBeVisible();
  await page.goto(`/app/households/${manifest.household_external_id}/shopping-list`);

  await page.goto(`/app/households/${manifest.household_external_id}`);
  const oliveOilProductRow = page
    .locator('[data-testid^="product-card-"]')
    .filter({ hasText: "Olive oil" });
  await expect(oliveOilProductRow).toBeVisible();
  await oliveOilProductRow.getByRole("button", { name: "Edit" }).click();

  const editProductForm = page.getByTestId("pantry-product-form");
  await editProductForm.getByLabel("Product name").fill("Extra virgin olive oil");
  await editProductForm.getByLabel("Product notes").fill("Use for dressings and finishing.");
  await editProductForm.getByRole("button", { name: "Save product" }).click();

  await expect(page.locator('[data-testid^="product-card-"]').filter({ hasText: "Extra virgin olive oil" })).toBeVisible();
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
  await page.getByRole("button", { name: "Add gap to shopping list" }).click();
  await expect(page.getByText("Added the recipe gap to the active shopping list.")).toBeVisible();

  await page.getByRole("link", { name: "Open shopping list" }).click();
  const tomatoesShoppingItem = page
    .locator(".shopping-item-card")
    .filter({ hasText: "Tomatoes" })
    .first();
  await expect(tomatoesShoppingItem).toContainText("recipe gap");
  await expect(tomatoesShoppingItem).toContainText("Recipe gap · Weeknight Pasta");
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
  await expect(page.getByTestId(`product-card-${manifest.product_external_ids.spice_blend}`)).toContainText(
    "Spice Blend",
  );
  await expect(page.getByTestId(`product-card-${manifest.product_external_ids.spice_blend}`)).toContainText(
    "1 jar across 1 lot",
  );
  await expect(page.getByTestId(`product-card-${manifest.product_external_ids.tomatoes}`)).toContainText(
    "3 can across 1 lot",
  );
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
  await expect(page).toHaveURL(/\/login$/);
  await loginThroughApi(page, {
    email: manifest.admin_email,
    password: manifest.password
  });
  await dismissAdminWhatsNewIfVisible(page);

  await page.goto("/admin/ai");
  await expect(page.getByRole("heading", { name: "Provider Setup" })).toBeVisible();
  const providerType = page.locator('[aria-label="Provider type"]');
  const baseUrlField = page.locator('[aria-label="Base URL"]');
  const defaultModelField = page.locator('[aria-label="Default model"]');
  const apiKeyField = page.getByLabel("API key");
  await expect(page.getByRole("button", { name: "Save configuration" })).toHaveCount(0);
  await expect(providerType).toContainText("OpenAI");
  await expect(baseUrlField).toContainText("https://api.openai.com/v1");
  await expect(defaultModelField).toContainText("gpt-5.4-mini");

  const providerBox = await providerType.boundingBox();
  const baseUrlBox = await baseUrlField.boundingBox();
  const defaultModelBox = await defaultModelField.boundingBox();
  const apiKeyBox = await apiKeyField.boundingBox();
  expect(Math.abs((providerBox?.height ?? 0) - (baseUrlBox?.height ?? 0))).toBeLessThan(1);
  expect(Math.abs((baseUrlBox?.height ?? 0) - (defaultModelBox?.height ?? 0))).toBeLessThan(1);
  expect(Math.abs((defaultModelBox?.height ?? 0) - (apiKeyBox?.height ?? 0))).toBeLessThan(1);

  await expect(page.getByRole("button", { name: "Run health check" })).toBeDisabled();

  await page.locator(".ai-provider-model-action button").click();
  await expect(page.getByRole("button", { name: "Back" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Save" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Close" })).toHaveCount(0);
  await expect(page.getByText("Fastest / cheapest")).toBeVisible();
  await expect(page.getByText("Recommended default")).toBeVisible();
  await expect(page.getByText("Best quality")).toBeVisible();
  await expect(page.getByLabel("Model name")).toHaveValue("gpt-5.4-mini");
  await page.getByLabel("Model name").fill("gpt-4.1-mini");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(defaultModelField).toContainText("gpt-4.1-mini");
  await expect(page.getByRole("button", { name: "Run health check" })).toBeDisabled();

  await apiKeyField.fill("test-openai-key");
  await page.keyboard.press("Tab");
  await expect(page.getByText("Health check failed.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Run health check" })).toBeEnabled();

  await page.getByRole("button", { name: "Run health check" }).click();
  await expect(page.getByText("Health check failed.")).toBeVisible();

  await page.goto("/admin");
  await page.goto("/admin/ai");
  await expect(providerType).toContainText("OpenAI");
  await expect(baseUrlField).toContainText("https://api.openai.com/v1");
  await expect(page.getByRole("button", { name: "Save configuration" })).toHaveCount(0);

  await page.getByRole("button", { name: "Logout" }).click();
  await loginThroughApi(page, {
    email: manifest.member_email,
    password: manifest.password
  });

  await page.goto(`/app/households/${manifest.household_external_id}/ai`);
  await expect(
    page.getByText("Pantry could not authenticate with the AI provider.")
  ).toBeVisible();
});

test("admin ai settings persist across navigation and keep stored-key state visible", async ({
  page
}) => {
  await loginThroughApi(page, {
    email: manifest.admin_email,
    password: manifest.password
  });
  await dismissAdminWhatsNewIfVisible(page);

  await page.goto("/admin/ai");
  await expect(page.locator('[aria-label="Provider type"]')).toContainText("OpenAI");
  await page.locator(".ai-provider-model-action button").click();
  await page.getByText("Fastest / cheapest").click();
  await page.getByRole("button", { name: "Save" }).click();
  await page.getByLabel("API key").fill("sk-test-secret");
  await page.keyboard.press("Tab");

  await expect(page.getByText("Health check failed.")).toBeVisible();

  await page.goto("/admin");
  await page.goto("/admin/ai");

  await expect(page.locator('[aria-label="Provider type"]')).toContainText("OpenAI");
  await expect(page.locator('[aria-label="Base URL"]')).toContainText("https://api.openai.com/v1");
  await expect(page.locator('[aria-label="Default model"]')).toContainText("gpt-4.1-mini");
  await expect(page.getByLabel("API key")).toHaveValue("");
});

test("admin ai api key blur auto-saves and health-checks without opening the model chooser", async ({
  page
}) => {
  await loginThroughApi(page, {
    email: manifest.admin_email,
    password: manifest.password
  });
  await dismissAdminWhatsNewIfVisible(page);

  await page.goto("/admin/ai");

  const defaultModelField = page.locator('[aria-label="Default model"]');
  const apiKeyField = page.getByLabel("API key");
  const chooseModelButton = page.locator(".ai-provider-model-action button");

  await expect(defaultModelField).toContainText("gpt-5.4-mini");
  await expect(page.getByRole("button", { name: "Back" })).toHaveCount(0);

  await apiKeyField.fill("test-openai-key");
  await page.keyboard.press("Tab");

  await expect(page.getByText("Health check failed.")).toBeVisible();
  await expect(apiKeyField).toHaveValue("");
  await expect(defaultModelField).toContainText("gpt-5.4-mini");
  await expect(page.getByRole("button", { name: "Back" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Run health check" })).toBeEnabled();

  await chooseModelButton.click();
  await expect(page.getByRole("button", { name: "Back" })).toBeVisible();
});

test("platform admin can manage household memberships from the consolidated panel", async ({
  page
}) => {
  await loginThroughApi(page, {
    email: manifest.admin_email,
    password: manifest.password
  });
  await dismissAdminWhatsNewIfVisible(page);

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

  await page
    .locator('select[name="membership_household_external_id"]')
    .selectOption({ label: "Weekday Household" });

  const membershipForm = page.getByTestId("admin-manage-memberships-form");
  await membershipForm
    .locator('select[name="user_external_id"]')
    .selectOption({ label: "Weekday Member (weekday-member@example.com)" });
  await membershipForm.locator('select[name="role"]').selectOption({ label: "User" });
  await membershipForm.getByRole("button", { name: "Add member" }).click();

  await expect(page.getByText("Assigned weekday-member@example.com as User.")).toBeVisible();

  const weekdayMemberRow = page
    .locator(".household-member-row")
    .filter({ hasText: "weekday-member@example.com" });
  await expect(weekdayMemberRow).toBeVisible();
  await weekdayMemberRow.getByLabel("Role for Weekday Member").selectOption({
    label: "Household Admin"
  });
  await weekdayMemberRow.getByRole("button", { name: "Save role" }).click();

  await expect(
    page.getByText("Updated weekday-member@example.com to Household Admin.")
  ).toBeVisible();

  const householdsRow = page.locator("tr", { hasText: "Weekday Household" });
  await expect(householdsRow).toContainText("Weekday Member");
  await expect(householdsRow).toContainText("Household Admin");

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
  await expect(page.getByRole("button", { name: "Add product" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Manage rooms" })).toBeVisible();
});

test("platform admin sees a warning modal when removing the last household admin would be unsafe", async ({
  page
}) => {
  await loginThroughApi(page, {
    email: manifest.admin_email,
    password: manifest.password
  });
  await dismissAdminWhatsNewIfVisible(page);

  await page.goto("/admin/users");

  const createUserForm = page.getByTestId("admin-create-user-form");
  await createUserForm.getByLabel("Email").fill("solo-admin@example.com");
  await createUserForm.getByLabel("Display name").fill("Solo Admin");
  await createUserForm.getByLabel("Password", { exact: true }).fill(manifest.password);
  await createUserForm.getByLabel("Confirm password").fill(manifest.password);
  await createUserForm.getByRole("button", { name: "Create user" }).click();

  await page.goto("/admin/households");

  const createHouseholdForm = page.getByTestId("admin-create-household-form");
  await createHouseholdForm.getByLabel("Household name").fill("Solo Admin Household");
  await createHouseholdForm.getByRole("button", { name: "Create household" }).click();
  await expect(page.getByRole("cell", { name: "Solo Admin Household" })).toBeVisible();

  await page
    .locator('select[name="membership_household_external_id"]')
    .selectOption({ label: "Solo Admin Household" });

  const membershipForm = page.getByTestId("admin-manage-memberships-form");
  await membershipForm
    .locator('select[name="user_external_id"]')
    .selectOption({ label: "Solo Admin (solo-admin@example.com)" });
  await membershipForm.locator('select[name="role"]').selectOption({ label: "Admin" });
  await membershipForm.getByRole("button", { name: "Add member" }).click();
  await expect(page.getByText("Assigned solo-admin@example.com as Admin.")).toBeVisible();

  const soloAdminRow = page.locator(".household-member-row").filter({ hasText: "solo-admin@example.com" });
  await soloAdminRow.getByRole("button", { name: "Remove" }).click();

  const warningDialog = page.getByRole("dialog", { name: "Household admin required" });
  await expect(warningDialog).toContainText("would be left without a household admin");
  await warningDialog.getByRole("button", { name: "Understood" }).click();
  await expect(warningDialog).toHaveCount(0);
  await expect(soloAdminRow).toBeVisible();
});

test("platform admin can remove household members and delete a household with confirmation", async ({
  page
}) => {
  await loginThroughApi(page, {
    email: manifest.admin_email,
    password: manifest.password
  });
  await dismissAdminWhatsNewIfVisible(page);

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

  await page
    .locator('select[name="membership_household_external_id"]')
    .selectOption({ label: "Cleanup Household" });

  const membershipForm = page.getByTestId("admin-manage-memberships-form");
  await membershipForm
    .locator('select[name="user_external_id"]')
    .selectOption({ label: "Cleanup Member (cleanup-member@example.com)" });
  await membershipForm.locator('select[name="role"]').selectOption({ label: "User" });
  await membershipForm.getByRole("button", { name: "Add member" }).click();
  await expect(page.getByText("Assigned cleanup-member@example.com as User.")).toBeVisible();

  const cleanupMemberRow = page
    .locator(".household-member-row")
    .filter({ hasText: "cleanup-member@example.com" });
  await cleanupMemberRow.getByRole("button", { name: "Remove" }).click();

  const removeDialog = page.getByRole("dialog", { name: "Remove membership" });
  await expect(removeDialog).toContainText("Cleanup Household");
  await removeDialog.getByRole("button", { name: "Remove member" }).click();

  await expect(page.getByText("Household membership removed.")).toBeVisible();
  await expect(cleanupMemberRow).toHaveCount(0);

  const deleteForm = page.getByTestId("admin-household-delete-form");
  await deleteForm
    .locator('select[name="delete_household_external_id"]')
    .selectOption({ label: "Cleanup Household" });
  await deleteForm.getByLabel("Type the household name to confirm deletion").fill("Cleanup Household");
  await deleteForm.getByRole("button", { name: "Delete household" }).click();

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

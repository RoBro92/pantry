import { expect, test } from "@playwright/test";
import { loginThroughApi, reseedE2E, type E2ESeedManifest } from "./helpers";

let manifest: E2ESeedManifest;

test.beforeEach(() => {
  manifest = reseedE2E();
});

test("shared modal keeps keyboard focus inside the dialog and restores it on close", async ({
  page,
}) => {
  await loginThroughApi(page, {
    email: manifest.member_email,
    password: manifest.password,
  });

  await page.goto(`/app/households/${manifest.household_external_id}`);

  await page.getByText("Household admin tools").click();
  const manageRoomsTrigger = page.getByRole("button", { name: "Manage rooms" });
  await manageRoomsTrigger.focus();
  await expect(manageRoomsTrigger).toBeFocused();
  await manageRoomsTrigger.click();

  const dialog = page.getByRole("dialog", { name: "Manage rooms" });
  const closeButton = dialog.getByRole("button", { name: "Close" });
  const roomNameInput = dialog.getByLabel("Room name");

  await expect(dialog).toBeVisible();
  await expect(roomNameInput).toBeFocused();

  await page.keyboard.press("Shift+Tab");
  await expect(closeButton).toBeFocused();

  await page.keyboard.press("Tab");
  await expect(roomNameInput).toBeFocused();

  await closeButton.click();
  await expect(dialog).toBeHidden();
  await expect(manageRoomsTrigger).toBeFocused();
});

test("bulk-scan camera stays inline inside the parent dialog", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await loginThroughApi(page, {
    email: manifest.member_email,
    password: manifest.password,
  });

  await page.goto(`/app/households/${manifest.household_external_id}`);

  await page.getByRole("button", { name: "Bulk scan" }).click();

  const bulkDialog = page.getByRole("dialog", { name: "Bulk scan inventory items" });
  const captureField = bulkDialog.getByLabel("Barcode capture");
  const scanWithCameraButton = bulkDialog.getByRole("button", { name: "Scan with camera" });

  await expect(bulkDialog).toBeVisible();
  await expect(captureField).toBeFocused();

  await scanWithCameraButton.focus();
  await expect(scanWithCameraButton).toBeFocused();
  await scanWithCameraButton.click();

  const scannerPanel = bulkDialog.getByTestId("barcode-scanner-dialog");
  const manualBarcodeField = scannerPanel.getByLabel("Type or scan barcodes");

  await expect(page.getByRole("dialog")).toHaveCount(1);
  await expect(scannerPanel).toBeVisible();
  await expect(manualBarcodeField).toBeVisible();

  await bulkDialog.getByRole("button", { name: "Hide camera" }).click();

  await expect(scannerPanel).toBeHidden();
  await expect(bulkDialog.getByRole("button", { name: "Scan with camera" })).toBeVisible();
});

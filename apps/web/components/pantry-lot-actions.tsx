"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import type { PantryLocationSummary, PantryStockLotSummary } from "../lib/api-types";
import { postToApi } from "../lib/client-api";
import { StockLotAdjustDialog } from "./stock-lot-adjust-dialog";
import { StockLotDeleteDialog } from "./stock-lot-delete-dialog";
import { StockLotEditorDialog } from "./stock-lot-editor-dialog";
import { StockLotMoveDialog } from "./stock-lot-move-dialog";

type PantryLotActionsProps = {
  householdExternalId: string;
  lot: PantryStockLotSummary;
  locations: PantryLocationSummary[];
};

export function PantryLotActions({
  householdExternalId,
  lot,
  locations,
}: PantryLotActionsProps) {
  const router = useRouter();
  const [dialog, setDialog] = useState<"adjust" | "edit" | "move" | "delete" | null>(null);
  const [shoppingPending, setShoppingPending] = useState(false);
  const [shoppingError, setShoppingError] = useState<string | null>(null);

  async function addToShoppingList() {
    setShoppingPending(true);
    setShoppingError(null);
    try {
      await postToApi(`/api/households/${householdExternalId}/shopping-list/items`, {
        product_external_id: lot.product_external_id,
        quantity: lot.quantity,
        unit: lot.unit,
        note: lot.note,
        source_type: "pantry_product",
      });
      router.refresh();
    } catch (requestError) {
      setShoppingError(
        requestError instanceof Error ? requestError.message : "Could not add this lot to the shopping list.",
      );
    } finally {
      setShoppingPending(false);
    }
  }

  return (
    <>
      <div className="lot-actions" data-testid={`lot-actions-${lot.external_id}`}>
        <div className="lot-actions-row">
          <button type="button" className="ghost-button compact-button" onClick={() => setDialog("adjust")}>
            Adjust
          </button>
          <button type="button" className="ghost-button compact-button" onClick={() => setDialog("edit")}>
            Edit
          </button>
          <button type="button" className="ghost-button compact-button" onClick={() => setDialog("move")}>
            Move
          </button>
          <button
            type="button"
            className="ghost-button compact-button"
            disabled={shoppingPending}
            onClick={() => void addToShoppingList()}
          >
            {shoppingPending ? "Adding..." : "Buy again"}
          </button>
          <button type="button" className="ghost-button compact-button" onClick={() => setDialog("delete")}>
            Delete
          </button>
        </div>
        {shoppingError ? <p className="error-text compact-error">{shoppingError}</p> : null}
      </div>

      {dialog === "adjust" ? (
        <StockLotAdjustDialog
          householdExternalId={householdExternalId}
          lotExternalId={lot.external_id}
          productName={lot.product_name}
          quantity={lot.quantity}
          unit={lot.unit}
          locationExternalId={lot.location_external_id}
          purchasedOn={lot.purchased_on}
          expiresOn={lot.expires_on}
          note={lot.note}
          onClose={() => setDialog(null)}
        />
      ) : null}

      {dialog === "edit" ? (
        <StockLotEditorDialog
          householdExternalId={householdExternalId}
          locations={locations}
          productExternalId={lot.product_external_id}
          mode="edit"
          initialValues={{
            lotExternalId: lot.external_id,
            productName: lot.product_name,
            quantity: lot.quantity,
            unit: lot.unit,
            locationExternalId: lot.location_external_id,
            purchasedOn: lot.purchased_on,
            expiresOn: lot.expires_on,
            note: lot.note,
          }}
          onClose={() => setDialog(null)}
        />
      ) : null}

      {dialog === "move" ? (
        <StockLotMoveDialog
          householdExternalId={householdExternalId}
          lotExternalId={lot.external_id}
          currentLocationExternalId={lot.location_external_id}
          currentQuantity={lot.quantity}
          locations={locations}
          onClose={() => setDialog(null)}
        />
      ) : null}

      {dialog === "delete" ? (
        <StockLotDeleteDialog
          householdExternalId={householdExternalId}
          lotExternalId={lot.external_id}
          productName={lot.product_name}
          quantity={lot.quantity}
          unit={lot.unit}
          onClose={() => setDialog(null)}
        />
      ) : null}
    </>
  );
}

"use client";

import { useState } from "react";
import type { PantryLocationSummary, PantryStockLotSummary } from "../lib/api-types";
import { StockLotAdjustDialog } from "./stock-lot-adjust-dialog";
import { StockLotDeleteDialog } from "./stock-lot-delete-dialog";
import { ShoppingListAddDialog } from "./shopping-list-add-dialog";
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
  const [dialog, setDialog] = useState<"adjust" | "edit" | "move" | "delete" | null>(null);
  const [shoppingOpen, setShoppingOpen] = useState(false);

  return (
    <>
      <div className="lot-actions" data-testid={`lot-actions-${lot.external_id}`}>
        <div className="lot-actions-row">
          <button type="button" className="ghost-button compact-button" onClick={() => setDialog("adjust")}>
            Qty
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
            onClick={() => setShoppingOpen(true)}
          >
            Shop
          </button>
          <button type="button" className="ghost-button compact-button" onClick={() => setDialog("delete")}>
            Delete
          </button>
        </div>
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

      {shoppingOpen ? (
        <ShoppingListAddDialog
          householdExternalId={householdExternalId}
          productExternalId={lot.product_external_id}
          productName={lot.product_name}
          sourceType="pantry_product"
          defaultQuantity="1"
          defaultUnit={lot.unit}
          defaultNote={lot.note}
          defaultLocationExternalId={lot.location_external_id}
          onClose={() => setShoppingOpen(false)}
        />
      ) : null}
    </>
  );
}

"use client";

import { type ReactNode, useState } from "react";
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

type LotActionButtonProps = {
  label: string;
  intent?: "default" | "danger";
  onClick: () => void;
  children: ReactNode;
};

function LotActionButton({
  label,
  intent = "default",
  onClick,
  children,
}: LotActionButtonProps) {
  return (
    <button
      type="button"
      className={intent === "danger" ? "lot-action-button is-danger" : "lot-action-button"}
      aria-label={label}
      title={label}
      onClick={onClick}
    >
      {children}
      <span className="icon-button-label">{label}</span>
    </button>
  );
}

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
          <LotActionButton label="Adjust quantity" onClick={() => setDialog("adjust")}>
            <svg viewBox="0 0 20 20" aria-hidden="true">
              <path d="M10 4v12M4 10h12" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.7" />
            </svg>
          </LotActionButton>
          <LotActionButton label="Edit stock lot" onClick={() => setDialog("edit")}>
            <svg viewBox="0 0 20 20" aria-hidden="true">
              <path d="M4 14.5V16h1.5l8.2-8.2-1.5-1.5zm10.3-9.3 1.5 1.5" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" />
            </svg>
          </LotActionButton>
          <LotActionButton label="Move stock lot" onClick={() => setDialog("move")}>
            <svg viewBox="0 0 20 20" aria-hidden="true">
              <path d="M4 10h12M11 6l5 4-5 4" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.6" />
            </svg>
          </LotActionButton>
          <LotActionButton label="Buy again" onClick={() => setShoppingOpen(true)}>
            <svg viewBox="0 0 20 20" aria-hidden="true">
              <path d="M4.5 5.5h11l-1 6.5H6zM7 15.5h.01M13 15.5h.01M3.5 4h1.5l1 1.5" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" />
            </svg>
          </LotActionButton>
          <LotActionButton label="Delete stock lot" intent="danger" onClick={() => setDialog("delete")}>
            <svg viewBox="0 0 20 20" aria-hidden="true">
              <path d="M6.5 3.5h7l.5 2H17v1.5H3V5.5h3zM7 8.5v6M10 8.5v6M13 8.5v6M5.5 7h9l-.6 9.2a1 1 0 0 1-1 .8H7.1a1 1 0 0 1-1-.8z" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" />
            </svg>
          </LotActionButton>
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
          locations={locations}
          onClose={() => setShoppingOpen(false)}
        />
      ) : null}
    </>
  );
}

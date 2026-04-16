"use client";

import { useState } from "react";
import { ModalShell } from "./modal-shell";

type FinishAction = "return_to_active" | "delete";

type ShoppingTripFinishDialogProps = {
  tripName: string;
  unresolvedItemCount: number;
  pending: boolean;
  onConfirm: (action: FinishAction) => Promise<void> | void;
  onClose: () => void;
};

export function ShoppingTripFinishDialog({
  tripName,
  unresolvedItemCount,
  pending,
  onConfirm,
  onClose,
}: ShoppingTripFinishDialogProps) {
  const [selectedAction, setSelectedAction] = useState<FinishAction>("return_to_active");

  return (
    <ModalShell
      title={`Finish ${tripName}`}
      description="Choose what should happen to the remaining unresolved items before this trip moves into history."
      onClose={onClose}
    >
      <div className="stack">
        <div className="warning-callout">
          <strong>{unresolvedItemCount} unresolved item{unresolvedItemCount === 1 ? "" : "s"} remain</strong>
          <p>Purchased items will still write back to inventory as normal when you finish this trip.</p>
        </div>

        <label className="checkbox-row">
          <input
            type="radio"
            name="finish_trip_action"
            checked={selectedAction === "return_to_active"}
            onChange={() => setSelectedAction("return_to_active")}
          />
          <span>Return remaining items to the active shopping list.</span>
        </label>

        <label className="checkbox-row">
          <input
            type="radio"
            name="finish_trip_action"
            checked={selectedAction === "delete"}
            onChange={() => setSelectedAction("delete")}
          />
          <span>Delete the remaining unresolved items.</span>
        </label>

        <div className="page-actions">
          <button type="button" className="ghost-button" disabled={pending} onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="primary-button"
            disabled={pending}
            onClick={() => void onConfirm(selectedAction)}
          >
            {pending ? "Finishing..." : "Finish trip"}
          </button>
        </div>
      </div>
    </ModalShell>
  );
}

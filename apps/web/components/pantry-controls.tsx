"use client";

import { useState } from "react";
import type {
  PantryLocationGroupSummary,
  PantryLocationSummary,
} from "../lib/api-types";
import { PantryAddEntryDialog } from "./pantry-add-entry-dialog";
import { PantryRoomDialog } from "./pantry-room-dialog";
import { PantrySearchDialog } from "./pantry-search-dialog";

type PantryControlsProps = {
  householdExternalId: string;
  canAdminister: boolean;
  locationGroups: PantryLocationGroupSummary[];
  locations: PantryLocationSummary[];
  filters: {
    q: string | null;
    location_group_external_id: string | null;
    location_external_id: string | null;
  };
};

export function PantryControls({
  householdExternalId,
  canAdminister,
  locationGroups,
  locations,
  filters,
}: PantryControlsProps) {
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [isRoomOpen, setIsRoomOpen] = useState(false);
  const hasActiveSearch = Boolean(
    filters.q || filters.location_group_external_id || filters.location_external_id,
  );

  return (
    <>
      <section className="panel pantry-toolbar">
        <div className="pantry-toolbar-copy">
          <p className="eyebrow">Pantry actions</p>
          <h2>Browse, search, and add items from one place</h2>
          <p className="section-copy">
            Search by product name, alias, or barcode, add new pantry items in one flow, and
            optionally preview Open Food Facts details before saving.
          </p>
        </div>
        <div className="pantry-action-pills">
          <button type="button" className="primary-button" onClick={() => setIsAddOpen(true)}>
            Add product
          </button>
          <button type="button" className="ghost-button" onClick={() => setIsSearchOpen(true)}>
            Search
          </button>
          {canAdminister ? (
            <button type="button" className="ghost-button" onClick={() => setIsRoomOpen(true)}>
              Manage rooms
            </button>
          ) : null}
        </div>
        {hasActiveSearch ? (
          <div className="info-callout compact-callout">
            <strong>Search is active</strong>
            <p>
              {filters.q ? `Query: ${filters.q}. ` : ""}
              {filters.location_group_external_id ? "Room filter applied. " : ""}
              {filters.location_external_id ? "Storage location filter applied." : ""}
            </p>
          </div>
        ) : null}
      </section>

      {isAddOpen ? (
        <PantryAddEntryDialog
          householdExternalId={householdExternalId}
          canAdminister={canAdminister}
          locations={locations}
          onClose={() => setIsAddOpen(false)}
        />
      ) : null}

      {isSearchOpen ? (
        <PantrySearchDialog
          initialFilters={filters}
          rooms={locationGroups}
          locations={locations}
          onClose={() => setIsSearchOpen(false)}
        />
      ) : null}

      {isRoomOpen ? (
        <PantryRoomDialog
          householdExternalId={householdExternalId}
          rooms={locationGroups}
          onClose={() => setIsRoomOpen(false)}
        />
      ) : null}
    </>
  );
}

"use client";

import { useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import type { PantryLocationGroupSummary, PantryLocationSummary } from "../lib/api-types";
import { ModalShell } from "./modal-shell";

type PantrySearchDialogProps = {
  initialFilters: {
    q: string | null;
    location_group_external_id: string | null;
    location_external_id: string | null;
  };
  rooms: PantryLocationGroupSummary[];
  locations: PantryLocationSummary[];
  onClose: () => void;
};

export function PantrySearchDialog({
  initialFilters,
  rooms,
  locations,
  onClose,
}: PantrySearchDialogProps) {
  const pathname = usePathname();
  const router = useRouter();
  const [query, setQuery] = useState(initialFilters.q ?? "");
  const [roomExternalId, setRoomExternalId] = useState(initialFilters.location_group_external_id ?? "");
  const [locationExternalId, setLocationExternalId] = useState(
    initialFilters.location_external_id ?? "",
  );

  function applyFilters(nextQuery: string, nextRoomExternalId: string, nextLocationExternalId: string) {
    const params = new URLSearchParams();
    if (nextQuery.trim()) {
      params.set("q", nextQuery.trim());
    }
    if (nextRoomExternalId) {
      params.set("location_group_external_id", nextRoomExternalId);
    }
    if (nextLocationExternalId) {
      params.set("location_external_id", nextLocationExternalId);
    }
    const url = params.toString() ? `${pathname}?${params.toString()}` : pathname;
    router.push(url, { scroll: false });
    onClose();
  }

  return (
    <ModalShell
      title="Search pantry"
      description="Search by product name, alias, or barcode."
      onClose={onClose}
    >
      <form
        className="stack"
        data-testid="pantry-search-form"
        onSubmit={(event) => {
          event.preventDefault();
          applyFilters(query, roomExternalId, locationExternalId);
        }}
      >
        <label className="field">
          <span>Search</span>
          <input
            name="q"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Beef mince, ground beef, or barcode"
          />
        </label>

        <div className="content-grid">
          <label className="field">
            <span>Room</span>
            <select
              name="location_group_external_id"
              value={roomExternalId}
              onChange={(event) => {
                setRoomExternalId(event.target.value);
                setLocationExternalId("");
              }}
            >
              <option value="">All rooms</option>
              {rooms.map((room) => (
                <option key={room.external_id} value={room.external_id}>
                  {room.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Storage location</span>
            <select
              name="location_external_id"
              value={locationExternalId}
              onChange={(event) => setLocationExternalId(event.target.value)}
            >
              <option value="">All storage locations</option>
              {locations
                .filter(
                  (location) =>
                    !roomExternalId || location.location_group_external_id === roomExternalId,
                )
                .map((location) => (
                  <option key={location.external_id} value={location.external_id}>
                    {location.location_group_name} / {location.name}
                  </option>
                ))}
            </select>
          </label>
        </div>

        <div className="page-actions">
          <button type="submit" className="primary-button">
            Search
          </button>
          <button
            type="button"
            className="ghost-button"
            onClick={() => {
              setQuery("");
              setRoomExternalId("");
              setLocationExternalId("");
              applyFilters("", "", "");
            }}
          >
            Clear search
          </button>
        </div>
      </form>
    </ModalShell>
  );
}

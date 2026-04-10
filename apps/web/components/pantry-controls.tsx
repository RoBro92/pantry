"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useRef, useState } from "react";
import type {
  PantryCatalogProductSummary,
  PantryLocationGroupSummary,
  PantryLocationSummary,
} from "../lib/api-types";
import { PantryAddEntryDialog } from "./pantry-add-entry-dialog";
import { ProductIntelligenceRunDialog } from "./product-intelligence-run-dialog";
import { PantryRoomDialog } from "./pantry-room-dialog";

type PantryControlsProps = {
  householdExternalId: string;
  householdName: string;
  canAdminister: boolean;
  catalogProducts: PantryCatalogProductSummary[];
  locationGroups: PantryLocationGroupSummary[];
  locations: PantryLocationSummary[];
  counts: {
    location_group_count: number;
    location_count: number;
    product_count: number;
    near_expiry_lot_count: number;
    out_of_stock_product_count: number;
  };
  filters: {
    q: string | null;
    location_group_external_id: string | null;
    location_external_id: string | null;
    near_expiry_only: boolean;
  };
};

export function PantryControls({
  householdExternalId,
  householdName,
  canAdminister,
  catalogProducts,
  locationGroups,
  locations,
  counts,
  filters,
}: PantryControlsProps) {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const roomSelectRef = useRef<HTMLSelectElement | null>(null);
  const locationSelectRef = useRef<HTMLSelectElement | null>(null);
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [isRoomOpen, setIsRoomOpen] = useState(false);
  const [isProductIntelligenceOpen, setIsProductIntelligenceOpen] = useState(false);
  const [query, setQuery] = useState(filters.q ?? "");
  const [roomExternalId, setRoomExternalId] = useState(filters.location_group_external_id ?? "");
  const [locationExternalId, setLocationExternalId] = useState(filters.location_external_id ?? "");
  const [nearExpiryOnly, setNearExpiryOnly] = useState(filters.near_expiry_only);

  const hasActiveFilters = Boolean(
    filters.q ||
      filters.location_group_external_id ||
      filters.location_external_id ||
      filters.near_expiry_only,
  );

  function pushFilters(
    nextQuery: string,
    nextRoomExternalId: string,
    nextLocationExternalId: string,
    nextNearExpiryOnly: boolean,
  ) {
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
    if (nextNearExpiryOnly) {
      params.set("near_expiry_only", "true");
    }
    const pageSize = searchParams.get("page_size");
    if (pageSize) {
      params.set("page_size", pageSize);
    }
    params.set("page", "1");
    const url = params.toString() ? `${pathname}?${params.toString()}` : pathname;
    router.push(url, { scroll: false });
  }

  function clearFilters() {
    setQuery("");
    setRoomExternalId("");
    setLocationExternalId("");
    setNearExpiryOnly(false);
    pushFilters("", "", "", false);
  }

  return (
    <>
      <section className="panel pantry-actions-panel">
        <div className="pantry-actions-header">
          <div className="stack compact-stack">
            <p className="eyebrow">Pantry</p>
            <h1 className="pantry-page-title">{householdName}</h1>
            <p className="section-copy">
              Search by product name, alias, or barcode. 
            </p>
          </div>
          <div className="pantry-action-pills">
            <button type="button" className="primary-button" onClick={() => setIsAddOpen(true)}>
              Add product
            </button>
            {canAdminister ? (
              <button type="button" className="ghost-button" onClick={() => setIsRoomOpen(true)}>
                Manage rooms
              </button>
            ) : null}
            {canAdminister ? (
              <button
                type="button"
                className="ghost-button"
                onClick={() => setIsProductIntelligenceOpen(true)}
              >
                Product intelligence
              </button>
            ) : null}
            <Link
              href={`/app/households/${householdExternalId}/imports`}
              className="secondary-link compact-link"
            >
              View imports
            </Link>
            <Link
              href={`/app/households/${householdExternalId}/recipes`}
              className="secondary-link compact-link"
            >
              View recipes
            </Link>
            <Link
              href={`/app/households/${householdExternalId}/ai`}
              className="secondary-link compact-link"
            >
              View AI suggestions
            </Link>
          </div>
        </div>

        <form
          className="pantry-filter-bar"
          onSubmit={(event) => {
            event.preventDefault();
            pushFilters(query, roomExternalId, locationExternalId, nearExpiryOnly);
          }}
        >
          <label className="field pantry-filter-search">
            <span>Search products</span>
            <input
              name="q"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Beef mince, ground beef, or barcode"
            />
          </label>
          <label className="field">
            <span>Room</span>
            <select
              ref={roomSelectRef}
              name="location_group_external_id"
              value={roomExternalId}
              onChange={(event) => {
                setRoomExternalId(event.target.value);
                setLocationExternalId("");
              }}
            >
              <option value="">All rooms</option>
              {locationGroups.map((room) => (
                <option key={room.external_id} value={room.external_id}>
                  {room.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Storage location</span>
            <select
              ref={locationSelectRef}
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
          <label className="checkbox-row pantry-filter-toggle">
            <input
              type="checkbox"
              name="near_expiry_only"
              checked={nearExpiryOnly}
              onChange={(event) => setNearExpiryOnly(event.target.checked)}
            />
            <span>Near expiry only</span>
          </label>
          <div className="pantry-filter-actions">
            <button type="submit" className="primary-button compact-button">
              Apply
            </button>
            <button type="button" className="ghost-button compact-button" onClick={clearFilters}>
              Clear
            </button>
          </div>
        </form>

        <div className="pantry-metric-chips" aria-label="Pantry quick filters">
          <button
            type="button"
            className="metric-chip"
            onClick={() => roomSelectRef.current?.focus()}
          >
            <span className="metric-chip-label">Rooms</span>
            <strong>{counts.location_group_count}</strong>
          </button>
          <button
            type="button"
            className="metric-chip"
            onClick={() => locationSelectRef.current?.focus()}
          >
            <span className="metric-chip-label">Storage locations</span>
            <strong>{counts.location_count}</strong>
          </button>
          <button type="button" className="metric-chip" onClick={clearFilters}>
            <span className="metric-chip-label">Products</span>
            <strong>{counts.product_count}</strong>
          </button>
          <button
            type="button"
            className={`metric-chip${counts.near_expiry_lot_count > 0 ? " is-warning" : ""}`}
            onClick={() => {
              const nextValue = !nearExpiryOnly;
              setNearExpiryOnly(nextValue);
              pushFilters(query, roomExternalId, locationExternalId, nextValue);
            }}
          >
            <span className="metric-chip-label">Near expiry</span>
            <strong>{counts.near_expiry_lot_count}</strong>
          </button>
        </div>

        <div className="pantry-toolbar-footnote">
          {hasActiveFilters ? (
            <p className="helper-text">
              Active filters stay focused on the main product list. Out of stock products remain
              visible unless you narrow the results further.
            </p>
          ) : (
            <p className="helper-text">
              {counts.out_of_stock_product_count > 0
                ? `${counts.out_of_stock_product_count} saved product record${counts.out_of_stock_product_count === 1 ? "" : "s"} currently have no active stock lots.`
                : "Search stays product focussed and matching products will group together."}
            </p>
          )}
        </div>
      </section>

      {isAddOpen ? (
        <PantryAddEntryDialog
          householdExternalId={householdExternalId}
          canAdminister={canAdminister}
          locations={locations}
          onClose={() => setIsAddOpen(false)}
        />
      ) : null}

      {isRoomOpen ? (
        <PantryRoomDialog
          householdExternalId={householdExternalId}
          rooms={locationGroups}
          onClose={() => setIsRoomOpen(false)}
        />
      ) : null}

      {isProductIntelligenceOpen ? (
        <ProductIntelligenceRunDialog
          householdExternalId={householdExternalId}
          catalogProducts={catalogProducts}
          onClose={() => setIsProductIntelligenceOpen(false)}
        />
      ) : null}
    </>
  );
}

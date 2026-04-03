"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import type {
  PantryCatalogProductSummary,
  PantryLocationGroupSummary,
  PantryLocationSummary
} from "../lib/api-types";
import { postToApi } from "../lib/client-api";

type PantryControlsProps = {
  householdExternalId: string;
  canAdminister: boolean;
  locationGroups: PantryLocationGroupSummary[];
  locations: PantryLocationSummary[];
  products: PantryCatalogProductSummary[];
};

type FormState = {
  error: string | null;
  success: string | null;
  pending: boolean;
};

function useFormState(): [FormState, (state: FormState) => void] {
  return useState<FormState>({ error: null, success: null, pending: false });
}

function splitListInput(value: string): string[] {
  return value
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function PantryControls({
  householdExternalId,
  canAdminister,
  locationGroups,
  locations,
  products
}: PantryControlsProps) {
  const router = useRouter();
  const [groupState, setGroupState] = useFormState();
  const [locationState, setLocationState] = useFormState();
  const [productState, setProductState] = useFormState();
  const [lotState, setLotState] = useFormState();

  async function submitForm(
    event: FormEvent<HTMLFormElement>,
    path: string,
    payload: Record<string, unknown>,
    setState: (state: FormState) => void
  ) {
    event.preventDefault();
    const form = event.currentTarget;
    setState({ error: null, success: null, pending: true });

    try {
      await postToApi(path, payload);
      form.reset();
      router.refresh();
      setState({ error: null, success: "Saved.", pending: false });
    } catch (error) {
      setState({
        error: error instanceof Error ? error.message : "Request failed.",
        success: null,
        pending: false
      });
    }
  }

  return (
    <section className="control-grid">
      {canAdminister ? (
        <>
          <form
            className="panel control-card"
            data-testid="create-group-form"
            onSubmit={(event) =>
              submitForm(
                event,
                `/api/households/${householdExternalId}/location-groups`,
                {
                  name: String(new FormData(event.currentTarget).get("name") ?? "")
                },
                setGroupState
              )}
          >
            <p className="eyebrow">Locations</p>
            <h2>Create group</h2>
            <label className="field">
              <span>Group name</span>
              <input name="name" placeholder="Kitchen pantry" required />
            </label>
            {groupState.error ? <p className="error-text">{groupState.error}</p> : null}
            {groupState.success ? <p className="status-note">{groupState.success}</p> : null}
            <button type="submit" className="primary-button" disabled={groupState.pending}>
              {groupState.pending ? "Saving..." : "Add group"}
            </button>
          </form>

          <form
            className="panel control-card"
            data-testid="create-location-form"
            onSubmit={(event) =>
              submitForm(
                event,
                `/api/households/${householdExternalId}/locations`,
                {
                  location_group_external_id: String(
                    new FormData(event.currentTarget).get("location_group_external_id") ?? ""
                  ),
                  name: String(new FormData(event.currentTarget).get("name") ?? "")
                },
                setLocationState
              )}
          >
            <p className="eyebrow">Locations</p>
            <h2>Create location</h2>
            <label className="field">
              <span>Group</span>
              <select name="location_group_external_id" required>
                <option value="">Select a group</option>
                {locationGroups.map((group) => (
                  <option key={group.external_id} value={group.external_id}>
                    {group.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Location name</span>
              <input name="name" placeholder="Top shelf" required />
            </label>
            {locationGroups.length === 0 ? (
              <p className="section-copy">Create a location group first.</p>
            ) : null}
            {locationState.error ? <p className="error-text">{locationState.error}</p> : null}
            {locationState.success ? <p className="status-note">{locationState.success}</p> : null}
            <button
              type="submit"
              className="primary-button"
              disabled={locationState.pending || locationGroups.length === 0}
            >
              {locationState.pending ? "Saving..." : "Add location"}
            </button>
          </form>

          <form
            className="panel control-card"
            data-testid="create-product-form"
            onSubmit={(event) => {
              const formData = new FormData(event.currentTarget);
              return submitForm(
                event,
                `/api/households/${householdExternalId}/products`,
                {
                  name: String(formData.get("name") ?? ""),
                  default_unit: String(formData.get("default_unit") ?? ""),
                  aliases: splitListInput(String(formData.get("aliases") ?? "")),
                  barcodes: splitListInput(String(formData.get("barcodes") ?? ""))
                },
                setProductState
              );
            }}
          >
            <p className="eyebrow">Products</p>
            <h2>Create product</h2>
            <label className="field">
              <span>Product name</span>
              <input name="name" placeholder="Pasta" required />
            </label>
            <label className="field">
              <span>Unit</span>
              <input name="default_unit" placeholder="count" required />
            </label>
            <label className="field">
              <span>Aliases</span>
              <textarea name="aliases" rows={3} placeholder="Spaghetti, dry pasta" />
            </label>
            <label className="field">
              <span>Barcodes</span>
              <textarea name="barcodes" rows={2} placeholder="0123456789012" />
            </label>
            {productState.error ? <p className="error-text">{productState.error}</p> : null}
            {productState.success ? <p className="status-note">{productState.success}</p> : null}
            <button type="submit" className="primary-button" disabled={productState.pending}>
              {productState.pending ? "Saving..." : "Add product"}
            </button>
          </form>
        </>
      ) : (
        <article className="panel control-card">
          <p className="eyebrow">Structure</p>
          <h2>Household-admin actions only</h2>
          <p className="section-copy">
            Creating location groups, locations, and catalog products requires the
            <code>household_admin</code> role. You can still add, move, and remove stock in the
            locations and products that already exist.
          </p>
        </article>
      )}

      <form
        className="panel control-card"
        data-testid="add-stock-form"
        onSubmit={(event) => {
          const formData = new FormData(event.currentTarget);
          const purchasedOn = String(formData.get("purchased_on") ?? "");
          const expiresOn = String(formData.get("expires_on") ?? "");

          return submitForm(
            event,
            `/api/households/${householdExternalId}/stock-lots`,
            {
              product_external_id: String(formData.get("product_external_id") ?? ""),
              location_external_id: String(formData.get("location_external_id") ?? ""),
              quantity: String(formData.get("quantity") ?? ""),
              note: String(formData.get("note") ?? "").trim() || null,
              purchased_on: purchasedOn || null,
              expires_on: expiresOn || null
            },
            setLotState
          );
        }}
      >
        <p className="eyebrow">Stock</p>
        <h2>Add stock lot</h2>
        <label className="field">
          <span>Product</span>
          <select name="product_external_id" required>
            <option value="">Select a product</option>
            {products.map((product) => (
              <option key={product.external_id} value={product.external_id}>
                {product.name}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Location</span>
          <select name="location_external_id" required>
            <option value="">Select a location</option>
            {locations.map((location) => (
              <option key={location.external_id} value={location.external_id}>
                {location.location_group_name} / {location.name}
              </option>
            ))}
          </select>
        </label>
        {products.length === 0 || locations.length === 0 ? (
          <p className="section-copy">
            Stock can be added after at least one product and one location exist for this household.
          </p>
        ) : null}
        <div className="split-fields">
          <label className="field">
            <span>Quantity</span>
            <input name="quantity" type="number" min="0.001" step="0.001" required />
          </label>
          <label className="field">
            <span>Purchased</span>
            <input name="purchased_on" type="date" />
          </label>
          <label className="field">
            <span>Expiry</span>
            <input name="expires_on" type="date" />
          </label>
        </div>
        <label className="field">
          <span>Note</span>
          <input name="note" placeholder="Market run, case discount, opened" />
        </label>
        {lotState.error ? <p className="error-text">{lotState.error}</p> : null}
        {lotState.success ? <p className="status-note">{lotState.success}</p> : null}
        <button
          type="submit"
          className="primary-button"
          disabled={lotState.pending || products.length === 0 || locations.length === 0}
        >
          {lotState.pending ? "Saving..." : "Add stock"}
        </button>
      </form>
    </section>
  );
}

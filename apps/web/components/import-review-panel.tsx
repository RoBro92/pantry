"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type {
  ImportDetail,
  ImportDetailResponse,
  ImportLineSummary,
  PantryLocationSummary,
  PantryProductOptionSummary,
} from "../lib/api-types";
import { postToApi, putToApi } from "../lib/client-api";

type ImportReviewPanelProps = {
  householdExternalId: string;
  importJob: ImportDetail;
  products: PantryProductOptionSummary[];
  locations: PantryLocationSummary[];
};

type ImportLineEditorProps = {
  householdExternalId: string;
  importExternalId: string;
  line: ImportLineSummary;
  products: PantryProductOptionSummary[];
  locked: boolean;
};

function ImportLineEditor({
  householdExternalId,
  importExternalId,
  line,
  products,
  locked
}: ImportLineEditorProps) {
  const router = useRouter();
  const [rawLabel, setRawLabel] = useState(line.raw_label);
  const [quantity, setQuantity] = useState(line.quantity);
  const [unit, setUnit] = useState(line.unit);
  const [barcode, setBarcode] = useState(line.barcode ?? "");
  const [note, setNote] = useState(line.note ?? "");
  const [productExternalId, setProductExternalId] = useState(line.product?.external_id ?? "");
  const [status, setStatus] = useState(line.status);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  async function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError(null);
    setSuccess(null);

    try {
      await putToApi<ImportDetailResponse>(
        `/api/households/${householdExternalId}/imports/${importExternalId}/lines/${line.external_id}`,
        {
          raw_label: rawLabel,
          quantity,
          unit,
          barcode: barcode.trim() || null,
          note: note.trim() || null,
          product_external_id: productExternalId || null,
          status
        }
      );
      setSuccess("Line saved. Refreshing import state...");
      router.refresh();
    } catch (submissionError) {
      setError(submissionError instanceof Error ? submissionError.message : "Save failed.");
      setPending(false);
    }
  }

  return (
    <form
      className="import-line-card"
      onSubmit={handleSave}
      data-testid={`import-line-${line.external_id}`}
    >
      <div className="page-actions">
        <div>
          <strong>
            Line {line.position}: {line.raw_label}
          </strong>
          <p className="section-copy">
            {line.source_reference ?? "No source reference"} · current status {line.status}
          </p>
        </div>
        {line.confirmed_stock_lot_external_id ? (
          <span className="tag">Lot {line.confirmed_stock_lot_external_id}</span>
        ) : null}
      </div>

      <div className="tag-row">
        <span className="tag">Current match: {line.product?.name ?? "None"}</span>
        <span className="tag subtle-tag">
          Suggested: {line.suggested_product?.name ?? "No suggestion"}
        </span>
        <span className="tag subtle-tag">Match basis: {line.match_basis}</span>
      </div>

      <div className="import-line-grid">
        <label className="field">
          <span>Label</span>
          <input value={rawLabel} onChange={(event) => setRawLabel(event.target.value)} disabled={locked} />
        </label>
        <label className="field">
          <span>Quantity</span>
          <input
            type="number"
            min="0.001"
            step="0.001"
            value={quantity}
            onChange={(event) => setQuantity(event.target.value)}
            disabled={locked}
          />
        </label>
        <label className="field">
          <span>Unit</span>
          <input value={unit} onChange={(event) => setUnit(event.target.value)} disabled={locked} />
        </label>
        <label className="field">
          <span>Barcode</span>
          <input value={barcode} onChange={(event) => setBarcode(event.target.value)} disabled={locked} />
        </label>
        <label className="field">
          <span>Match product</span>
          <select
            value={productExternalId}
            onChange={(event) => setProductExternalId(event.target.value)}
            disabled={locked}
          >
            <option value="">No product selected</option>
            {products.map((product) => (
              <option key={product.external_id} value={product.external_id}>
                {product.name} ({product.default_unit})
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Status</span>
          <select value={status} onChange={(event) => setStatus(event.target.value as typeof status)} disabled={locked}>
            <option value="matched">Matched</option>
            <option value="needs_review">Needs review</option>
            <option value="unresolved">Unresolved</option>
            <option value="ignored">Ignored</option>
          </select>
        </label>
      </div>

      <label className="field">
        <span>Note</span>
        <input
          value={note}
          onChange={(event) => setNote(event.target.value)}
          placeholder="Manual correction or receipt context"
          disabled={locked}
        />
      </label>
      {error ? <p className="error-text compact-error">{error}</p> : null}
      {success ? <p className="status-note">{success}</p> : null}
      <div className="page-actions">
        <button type="submit" className="primary-button" disabled={locked || pending}>
          {pending ? "Saving..." : "Save line"}
        </button>
      </div>
    </form>
  );
}

export function ImportReviewPanel({
  householdExternalId,
  importJob,
  products,
  locations
}: ImportReviewPanelProps) {
  const router = useRouter();
  const [locationExternalId, setLocationExternalId] = useState(locations[0]?.external_id ?? "");
  const [purchasedOn, setPurchasedOn] = useState(importJob.occurred_on ?? "");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const locked = importJob.status === "confirmed" || importJob.status === "failed";

  async function handleConfirm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError(null);
    setSuccess(null);

    try {
      await postToApi<ImportDetailResponse>(
        `/api/households/${householdExternalId}/imports/${importJob.external_id}/confirm`,
        {
          location_external_id: locationExternalId,
          purchased_on: purchasedOn || null
        }
      );
      setSuccess("Import confirmed. Refreshing pantry state...");
      router.refresh();
    } catch (submissionError) {
      setError(submissionError instanceof Error ? submissionError.message : "Confirmation failed.");
      setPending(false);
    }
  }

  return (
    <section className="stack">
      <article className="panel">
        <p className="eyebrow">Review Lines</p>
        {importJob.status === "queued" || importJob.status === "processing" ? (
          <p className="section-copy">
            The worker is still processing this upload. Refresh this page after processing completes.
          </p>
        ) : null}
        {importJob.status === "failed" ? (
          <p className="error-text">
            This import failed before review. Check the lifecycle details above and upload a corrected
            source file if needed.
          </p>
        ) : null}
        {importJob.lines.length === 0 ? (
          <p>No import lines are available yet. Refresh after the worker finishes processing.</p>
        ) : (
          <div className="import-line-list">
            {importJob.lines.map((line) => (
              <ImportLineEditor
                key={line.external_id}
                householdExternalId={householdExternalId}
                importExternalId={importJob.external_id}
                line={line}
                products={products}
                locked={locked}
              />
            ))}
          </div>
        )}
      </article>

      <article className="panel">
        <p className="eyebrow">Confirm To Pantro</p>
        {locations.length === 0 ? (
          <p>
            Create a pantry location before confirming this import.{" "}
            <Link href={`/app/households/${householdExternalId}`} className="inline-link">
              Go to pantry setup
            </Link>
            .
          </p>
        ) : (
          <form className="stack" onSubmit={handleConfirm} data-testid="confirm-import-form">
            <div className="recipe-form-grid">
              <label className="field">
                <span>Destination location</span>
                <select
                  value={locationExternalId}
                  onChange={(event) => setLocationExternalId(event.target.value)}
                  disabled={locked}
                >
                  <option value="">Select a location</option>
                  {locations.map((location) => (
                    <option key={location.external_id} value={location.external_id}>
                      {location.location_group_name} / {location.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>Fallback purchased date</span>
                <input
                  type="date"
                  value={purchasedOn}
                  onChange={(event) => setPurchasedOn(event.target.value)}
                  disabled={locked}
                />
              </label>
            </div>
            <p className="section-copy">
              Confirmation is the only step that writes to pantry stock. Every non-ignored line must
              be resolved first.
            </p>
            {error ? <p className="error-text">{error}</p> : null}
            {success ? <p className="status-note">{success}</p> : null}
            <div className="page-actions">
              <button
                type="submit"
                className="primary-button"
                disabled={
                  locked ||
                  pending ||
                  !importJob.ready_to_confirm ||
                  !locationExternalId ||
                  locations.length === 0
                }
              >
                {pending ? "Confirming..." : "Confirm import"}
              </button>
              {!importJob.ready_to_confirm && !locked ? (
                <span className="tag subtle-tag">
                  {importJob.blocking_line_count} line
                  {importJob.blocking_line_count === 1 ? "" : "s"} still need review
                </span>
              ) : null}
            </div>
          </form>
        )}
      </article>
    </section>
  );
}

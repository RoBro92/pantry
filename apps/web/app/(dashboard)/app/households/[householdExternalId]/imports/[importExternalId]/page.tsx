import Link from "next/link";
import { ImportReviewPanel } from "../../../../../../../components/import-review-panel";
import { StatusCard } from "../../../../../../../components/status-card";
import {
  getImportDetail,
  getPantryLocationOptions,
  getPantryProductOptions,
  requireHouseholdAccess
} from "../../../../../../../lib/server-auth";

type ImportDetailPageProps = {
  params: Promise<{
    householdExternalId: string;
    importExternalId: string;
  }>;
};

export default async function ImportDetailPage({ params }: ImportDetailPageProps) {
  const { householdExternalId, importExternalId } = await params;
  await requireHouseholdAccess(householdExternalId);
  const [response, pantryProducts, pantryLocations] = await Promise.all([
    getImportDetail(householdExternalId, importExternalId),
    getPantryProductOptions(householdExternalId),
    getPantryLocationOptions(householdExternalId),
  ]);
  const importJob = response.import_job;

  return (
    <div className="stack">
      <section className="panel">
        <p className="eyebrow">Import Detail</p>
        <div className="page-actions">
          <div>
            <h1>{importJob.source_label}</h1>
            <p>
              {importJob.source_type} · status {importJob.status} · created{" "}
              {new Date(importJob.created_at).toLocaleString("en-GB", {
                dateStyle: "medium",
                timeStyle: "short"
              })}
            </p>
          </div>
          <div className="tag-row">
            {importJob.parser_kind ? <span className="tag">Parser {importJob.parser_kind}</span> : null}
            <span className="tag subtle-tag">
              Requested by {importJob.requested_by_display ?? "Unknown actor"}
            </span>
          </div>
        </div>
        {importJob.note ? <p>{importJob.note}</p> : null}
        <div className="page-actions">
          <Link href={`/app/households/${householdExternalId}/imports`} className="secondary-link">
            Back to imports
          </Link>
          <Link
            href={`/app/households/${householdExternalId}/imports/${importJob.external_id}`}
            className="secondary-link"
          >
            Refresh
          </Link>
          <Link href={`/app/households/${householdExternalId}`} className="secondary-link">
            Inventory
          </Link>
        </div>
      </section>

      <section className="status-grid">
        <StatusCard
          title="Matched"
          value={String(importJob.counts.matched_line_count)}
          detail="Lines currently ready for confirmation."
        />
        <StatusCard
          title="Needs Review"
          value={String(importJob.counts.needs_review_line_count)}
          detail="Lines explicitly held for manual review."
        />
        <StatusCard
          title="Unresolved"
          value={String(importJob.counts.unresolved_line_count)}
          detail="Lines without a product match yet."
        />
        <StatusCard
          title="Confirmed"
          value={String(importJob.counts.confirmed_line_count)}
          detail="Lines already written into inventory stock lots."
        />
      </section>

      <section className="content-grid">
        <article className="panel">
          <p className="eyebrow">Source Files</p>
          {importJob.source_files.length === 0 ? (
            <p>No source files were recorded for this import.</p>
          ) : (
            <ul className="detail-list">
              {importJob.source_files.map((sourceFile) => (
                <li key={sourceFile.external_id}>
                  <strong>{sourceFile.original_filename}</strong>
                  <span>
                    {sourceFile.detected_content_type ?? sourceFile.client_content_type ?? "Unknown type"} ·{" "}
                    {sourceFile.size_bytes} bytes
                  </span>
                  {sourceFile.note ? <span>{sourceFile.note}</span> : null}
                </li>
              ))}
            </ul>
          )}
        </article>

        <article className="panel">
          <p className="eyebrow">Lifecycle</p>
          <ul className="detail-list">
            <li>
              <strong>Occurred on</strong>
              <span>{importJob.occurred_on ?? "Not set"}</span>
            </li>
            <li>
              <strong>Processed at</strong>
              <span>{importJob.processed_at ?? "Waiting for worker"}</span>
            </li>
            <li>
              <strong>Confirmed at</strong>
              <span>{importJob.confirmed_at ?? "Not confirmed"}</span>
            </li>
            <li>
              <strong>Household role</strong>
              <span>{response.effective_role}</span>
            </li>
          </ul>
          {importJob.failure_message ? <p className="error-text">{importJob.failure_message}</p> : null}
        </article>
      </section>

      <ImportReviewPanel
        householdExternalId={householdExternalId}
        importJob={importJob}
        products={pantryProducts.products}
        locations={pantryLocations.locations}
      />
    </div>
  );
}

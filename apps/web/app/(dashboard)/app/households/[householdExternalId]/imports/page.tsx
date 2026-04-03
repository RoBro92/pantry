import Link from "next/link";
import { ImportUploadForm } from "../../../../../../components/import-upload-form";
import { StatusCard } from "../../../../../../components/status-card";
import { getImportList, requireSession } from "../../../../../../lib/server-auth";

type ImportListPageProps = {
  params: Promise<{
    householdExternalId: string;
  }>;
};

export default async function HouseholdImportListPage({ params }: ImportListPageProps) {
  await requireSession();
  const { householdExternalId } = await params;
  const response = await getImportList(householdExternalId);

  return (
    <div className="stack">
      <section className="panel">
        <p className="eyebrow">Imports</p>
        <h1>{response.household_name}</h1>
        <p>
          Imports stay review-first. Uploads and parsed lines are tracked separately from pantry
          stock, and nothing changes inventory until a reviewed import is explicitly confirmed.
        </p>
        <div className="page-actions">
          <Link href={`/app/households/${response.household_external_id}`} className="secondary-link">
            Back to pantry
          </Link>
        </div>
      </section>

      <section className="status-grid">
        <StatusCard
          title="Total Imports"
          value={String(response.imports.length)}
          detail="All household import jobs, including queued and historical runs."
        />
        <StatusCard
          title="Needs Review"
          value={String(response.imports.filter((item) => item.status === "needs_review").length)}
          detail="Imports ready for manual line review before pantry writes."
        />
        <StatusCard
          title="Confirmed"
          value={String(response.imports.filter((item) => item.status === "confirmed").length)}
          detail="Reviewed imports that have already created stock lots."
        />
        <StatusCard
          title="Failed"
          value={String(response.imports.filter((item) => item.status === "failed").length)}
          detail="Imports that need a new upload or parser support."
        />
      </section>

      <ImportUploadForm householdExternalId={response.household_external_id} />

      <section className="panel">
        <p className="eyebrow">Inbox And History</p>
        {response.imports.length === 0 ? (
          <div className="stack">
            <p>No imports have been created for this household yet.</p>
            <p className="section-copy">
              Start with a structured CSV, TSV, JSON, or text export. Review stays separate from
              pantry stock until you explicitly confirm a cleaned-up import.
            </p>
          </div>
        ) : (
          <div className="recipe-card-grid">
            {response.imports.map((item) => (
              <article key={item.external_id} className="recipe-card">
                <div className="page-actions">
                  <div>
                    <h2>{item.source_label}</h2>
                    <p>
                      {item.source_type} · status {item.status} · created{" "}
                      {new Date(item.created_at).toLocaleString("en-GB", {
                        dateStyle: "medium",
                        timeStyle: "short"
                      })}
                    </p>
                  </div>
                  <div className="tag-row">
                    <span className="tag">{item.counts.line_count} lines</span>
                    <span className="tag">{item.counts.matched_line_count} matched</span>
                    <span className="tag subtle-tag">{item.counts.unresolved_line_count} unresolved</span>
                  </div>
                </div>
                {item.note ? <p>{item.note}</p> : null}
                {item.failure_message ? <p className="error-text">{item.failure_message}</p> : null}
                {item.status === "queued" || item.status === "processing" ? (
                  <p className="section-copy">
                    Worker processing is still in progress. Open the detail page to refresh the line
                    review state.
                  </p>
                ) : null}
                <div className="page-actions">
                  <Link
                    href={`/app/households/${response.household_external_id}/imports/${item.external_id}`}
                    className="primary-link"
                  >
                    Review import
                  </Link>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

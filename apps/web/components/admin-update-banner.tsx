import Link from "next/link";
import type { ReleaseCheckResponse } from "../lib/api-types";

type AdminUpdateBannerProps = {
  releaseStatus: ReleaseCheckResponse;
};

export function AdminUpdateBanner({ releaseStatus }: AdminUpdateBannerProps) {
  if (releaseStatus.status !== "update_available") {
    return null;
  }

  return (
    <section className="panel admin-update-banner" data-testid="admin-update-banner">
      <div className="stack">
        <p className="eyebrow">Update available</p>
        <h2>
          Pantry {releaseStatus.latest_version ?? "latest release"} is available for this
          installation
        </h2>
        <p className="section-copy">
          You are running {releaseStatus.current_version}. Review the update notes and manual
          operator steps before choosing when to upgrade.
        </p>
      </div>
      <div className="page-actions">
        <Link href="/admin/updates" className="primary-link">
          Review update
        </Link>
        {releaseStatus.release_notes_url ? (
          <a href={releaseStatus.release_notes_url} className="secondary-link">
            Release notes
          </a>
        ) : null}
      </div>
    </section>
  );
}

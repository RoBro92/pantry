import { AdminUpdatesPanel } from "../../../../components/admin-updates-panel";
import { getReleaseStatus } from "../../../../lib/server-auth";

export default async function AdminUpdatesPage() {
  const releaseStatus = await getReleaseStatus();

  return (
    <div className="stack">
      <section className="panel">
        <p className="eyebrow">Updates</p>
        <h1>Release Notes and updates</h1>
        <p>
          Review advisory release metadata, acknowledge changelog notes after upgrades, 
          and use the backup tools to export or restore Pantry data.
        </p>
      </section>
      <AdminUpdatesPanel initialReleaseStatus={releaseStatus} />
    </div>
  );
}

import { AdminUpdatesPanel } from "../../../../components/admin-updates-panel";
import { getReleaseStatus } from "../../../../lib/server-auth";

export default async function AdminUpdatesPage() {
  const releaseStatus = await getReleaseStatus();

  return (
    <div className="stack">
      <section className="panel">
        <p className="eyebrow">Updates</p>
        <h1>Release visibility and manual updates</h1>
        <p>
          Review advisory release metadata, acknowledge changelog notes after upgrades, and keep
          update and recovery actions in operator hands.
        </p>
      </section>
      <AdminUpdatesPanel initialReleaseStatus={releaseStatus} />
    </div>
  );
}

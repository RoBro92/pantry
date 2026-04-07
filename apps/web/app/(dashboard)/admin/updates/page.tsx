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
          Pantry only surfaces advisory release metadata here. Operators still control when to pull
          images, run migrations, and restart the stack.
        </p>
      </section>
      <AdminUpdatesPanel initialReleaseStatus={releaseStatus} />
    </div>
  );
}

import { AdminBackupsPanel } from "../../../../components/admin-backups-panel";
import { getAdminHouseholds } from "../../../../lib/server-auth";

export default async function AdminBackupsPage() {
  const households = await getAdminHouseholds();

  return (
    <div className="stack">
      <section className="panel">
        <p className="eyebrow">Backups</p>
        <h1>Export and recovery foundations</h1>
        <p>
          Export Pantry-native backup bundles for operator-controlled recovery. Import and restore
          actions stay explicit, validated, and deliberately destructive.
        </p>
      </section>
      <AdminBackupsPanel households={households} />
    </div>
  );
}

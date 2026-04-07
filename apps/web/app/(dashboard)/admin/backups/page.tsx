import { AdminBackupsPanel } from "../../../../components/admin-backups-panel";
import { getAdminHouseholds } from "../../../../lib/server-auth";

export default async function AdminBackupsPage() {
  const households = await getAdminHouseholds();

  return (
    <div className="stack">
      <section className="panel">
        <p className="eyebrow">Backups</p>
        <h1>Backup and Restore</h1>
        <p>
          Here you can create a backup for all data or selected households. You can also restore from a backup file.
        </p>
      </section>
      <AdminBackupsPanel households={households} />
    </div>
  );
}

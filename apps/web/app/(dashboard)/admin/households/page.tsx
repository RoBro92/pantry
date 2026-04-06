import Link from "next/link";
import { AdminHouseholdManagementPanel } from "../../../../components/admin-household-management-panel";
import { DataTable } from "../../../../components/data-table";
import { getHouseholdRoleLabel } from "../../../../lib/role-labels";
import { getAdminHouseholds, getAdminUsers } from "../../../../lib/server-auth";

export default async function AdminHouseholdsPage() {
  const [households, users] = await Promise.all([getAdminHouseholds(), getAdminUsers()]);

  return (
    <div className="stack">
      <AdminHouseholdManagementPanel households={households} users={users} />
      <DataTable
        title="Households"
        columns={["Name", "External ID", "Memberships", "Current Members", "Pantry"]}
      >
        {households.map((household) => (
          <tr key={household.external_id}>
            <td>{household.name}</td>
            <td>{household.external_id}</td>
            <td>{household.membership_count}</td>
            <td>
              {household.memberships.length === 0
                ? "None"
                : household.memberships
                    .map(
                      (membership) =>
                        `${membership.display_name ?? membership.email} (${getHouseholdRoleLabel(membership.role)})`,
                    )
                    .join(", ")}
            </td>
            <td>
              <Link href={`/app/households/${household.external_id}`} className="inline-link">
                Open pantry
              </Link>
            </td>
          </tr>
        ))}
      </DataTable>
    </div>
  );
}

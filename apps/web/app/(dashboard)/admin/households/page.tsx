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
        tableClassName="households-table"
      >
        {households.map((household) => (
          <tr key={household.external_id}>
            <td className="household-name-cell">
              <strong>{household.name}</strong>
            </td>
            <td className="household-external-id-cell">
              <code>{household.external_id}</code>
            </td>
            <td className="household-count-cell">{household.membership_count}</td>
            <td className="household-members-cell">
              {household.memberships.length === 0
                ? "None"
                : household.memberships.map((membership) => (
                    <div key={membership.membership_external_id} className="table-member-row">
                      <span>{membership.display_name ?? membership.email}</span>
                      <span className="table-member-role">
                        {getHouseholdRoleLabel(membership.role)}
                      </span>
                    </div>
                  ))}
            </td>
            <td className="household-link-cell">
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

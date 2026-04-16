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
        columns={["Name", "External ID", "Memberships", "Current Members", "Role", "Inventory"]}
        tableClassName="households-table"
      >
        {households.map((household) => {
          const adminCount = household.memberships.filter(
            (membership) => membership.role === "household_admin",
          ).length;

          return (
            <tr key={household.external_id}>
              <td data-label="Name" className="household-name-cell">
                <div className="household-table-stack">
                  <strong>{household.name}</strong>
                  <span className="helper-text">
                    {adminCount} {adminCount === 1 ? "admin" : "admins"}
                  </span>
                </div>
              </td>
              <td data-label="External ID" className="household-external-id-cell">
                <code>{household.external_id}</code>
              </td>
              <td data-label="Memberships" className="household-count-cell">
                {household.membership_count}
              </td>
              <td data-label="Current Members" className="household-members-cell">
                {household.memberships.length === 0 ? (
                  <span className="helper-text">None</span>
                ) : (
                  <div className="household-table-stack">
                    {household.memberships.map((membership) => (
                      <span key={membership.membership_external_id} className="household-table-entry">
                        {membership.display_name ?? membership.email}
                      </span>
                    ))}
                  </div>
                )}
              </td>
              <td data-label="Role" className="household-roles-cell">
                {household.memberships.length === 0 ? (
                  <span className="helper-text">-</span>
                ) : (
                  <div className="household-table-stack">
                    {household.memberships.map((membership) => (
                      <span key={membership.membership_external_id} className="household-table-entry">
                        {getHouseholdRoleLabel(membership.role, { detailed: true })}
                      </span>
                    ))}
                  </div>
                )}
              </td>
              <td data-label="Inventory" className="household-link-cell">
                <Link href={`/app/households/${household.external_id}`} className="inline-link">
                  Open inventory
                </Link>
              </td>
            </tr>
          );
        })}
      </DataTable>
    </div>
  );
}

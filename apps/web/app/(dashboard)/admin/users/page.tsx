import { AdminUserCreationForm } from "../../../../components/admin-user-creation-form";
import { DataTable } from "../../../../components/data-table";
import { getPlatformRoleLabel } from "../../../../lib/role-labels";
import { getAdminUsers } from "../../../../lib/server-auth";

export default async function AdminUsersPage() {
  const users = await getAdminUsers();

  return (
    <div className="stack">
      <AdminUserCreationForm />
      <DataTable
        title="Users"
        columns={["Sign-in ID", "Display Name", "Access", "Memberships", "Status"]}
      >
        {users.map((user) => (
          <tr key={user.external_id}>
            <td>{user.email}</td>
            <td>{user.display_name ?? "Unspecified"}</td>
            <td>{getPlatformRoleLabel(user.platform_role, { detailed: true })}</td>
            <td>{user.membership_count}</td>
            <td>{user.is_active ? "Active" : "Inactive"}</td>
          </tr>
        ))}
      </DataTable>
    </div>
  );
}

import { DataTable } from "../../../../components/data-table";
import { getAdminUsers, requirePlatformAdminSession } from "../../../../lib/server-auth";

export default async function AdminUsersPage() {
  await requirePlatformAdminSession();
  const users = await getAdminUsers();

  return (
    <DataTable title="Users" columns={["Email", "Display Name", "Platform Role", "Memberships", "Status"]}>
      {users.map((user) => (
        <tr key={user.external_id}>
          <td>{user.email}</td>
          <td>{user.display_name ?? "Unspecified"}</td>
          <td>{user.platform_role ?? "None"}</td>
          <td>{user.membership_count}</td>
          <td>{user.is_active ? "active" : "inactive"}</td>
        </tr>
      ))}
    </DataTable>
  );
}


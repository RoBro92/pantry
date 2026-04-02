import { DataTable } from "../../../../components/data-table";
import { getAdminHouseholds, requirePlatformAdminSession } from "../../../../lib/server-auth";

export default async function AdminHouseholdsPage() {
  await requirePlatformAdminSession();
  const households = await getAdminHouseholds();

  return (
    <DataTable title="Households" columns={["Name", "External ID", "Memberships"]}>
      {households.map((household) => (
        <tr key={household.external_id}>
          <td>{household.name}</td>
          <td>{household.external_id}</td>
          <td>{household.membership_count}</td>
        </tr>
      ))}
    </DataTable>
  );
}


import { AdminUserCreationForm } from "../../../../components/admin-user-creation-form";
import { AdminUserManagementPanel } from "../../../../components/admin-user-management-panel";
import { getAdminHouseholds, getAdminUsers, getSMTPConfig } from "../../../../lib/server-auth";

export default async function AdminUsersPage() {
  const [users, households, smtpConfig] = await Promise.all([
    getAdminUsers(),
    getAdminHouseholds(),
    getSMTPConfig(),
  ]);

  return (
    <div className="stack">
      <AdminUserCreationForm />
      <AdminUserManagementPanel
        users={users}
        households={households}
        passwordResetEnabled={smtpConfig.password_reset.is_available}
      />
    </div>
  );
}

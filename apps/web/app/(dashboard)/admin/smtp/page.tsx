import { AdminSMTPConfigForm } from "../../../../components/admin-smtp-config-form";
import { getSMTPConfig } from "../../../../lib/server-auth";

export default async function AdminSMTPPage() {
  const config = await getSMTPConfig();
  return <AdminSMTPConfigForm initialConfig={config} />;
}

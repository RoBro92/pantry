import { AdminSettingsForm } from "../../../../components/admin-settings-form";
import { getPublicBaseURL } from "../../../../lib/server-auth";

export default async function AdminSettingsPage() {
  const publicBaseUrl = await getPublicBaseURL();
  return <AdminSettingsForm initialPublicBaseUrl={publicBaseUrl} />;
}

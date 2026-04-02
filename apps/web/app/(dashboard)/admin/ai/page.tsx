import { AdminAIConfigForm } from "../../../../components/admin-ai-config-form";
import { getAIProviderConfig, requirePlatformAdminSession } from "../../../../lib/server-auth";

export default async function AdminAIPage() {
  await requirePlatformAdminSession();
  const config = await getAIProviderConfig();

  return <AdminAIConfigForm initialConfigResponse={config} />;
}

import { AdminAIConfigForm } from "../../../../components/admin-ai-config-form";
import { getAIProviderConfig } from "../../../../lib/server-auth";

export default async function AdminAIPage() {
  const config = await getAIProviderConfig();

  return <AdminAIConfigForm initialConfigResponse={config} />;
}

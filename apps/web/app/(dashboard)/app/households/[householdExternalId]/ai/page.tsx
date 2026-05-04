import { HouseholdAIMealPlanner } from "../../../../../../components/household-ai-meal-planner";
import {
  getAIMealPlanner,
  requireHouseholdAccess
} from "../../../../../../lib/server-auth";

type HouseholdAIPageProps = {
  params: Promise<{
    householdExternalId: string;
  }>;
};

export default async function HouseholdAIPage({ params }: HouseholdAIPageProps) {
  const { householdExternalId } = await params;
  const session = await requireHouseholdAccess(householdExternalId);
  const planner = await getAIMealPlanner(householdExternalId);

  return (
    <HouseholdAIMealPlanner
      householdExternalId={householdExternalId}
      initialPlanner={planner}
      isPlatformAdmin={session.user.platform_role === "platform_admin"}
    />
  );
}

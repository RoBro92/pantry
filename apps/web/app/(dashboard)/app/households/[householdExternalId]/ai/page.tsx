import { HouseholdAIMealPlanner } from "../../../../../../components/household-ai-meal-planner";
import {
  getAIMealPlanner,
  requireSession
} from "../../../../../../lib/server-auth";

type HouseholdAIPageProps = {
  params: Promise<{
    householdExternalId: string;
  }>;
};

export default async function HouseholdAIPage({ params }: HouseholdAIPageProps) {
  const session = await requireSession();
  const { householdExternalId } = await params;
  const planner = await getAIMealPlanner(householdExternalId);

  return (
    <HouseholdAIMealPlanner
      householdExternalId={householdExternalId}
      initialPlanner={planner}
      isPlatformAdmin={session.user.platform_role === "platform_admin"}
    />
  );
}

import { HouseholdAISuggestions } from "../../../../../../components/household-ai-suggestions";
import {
  getHouseholdAIStatus,
  getRecipeList,
  requireSession
} from "../../../../../../lib/server-auth";

type HouseholdAIPageProps = {
  params: Promise<{
    householdExternalId: string;
  }>;
};

export default async function HouseholdAIPage({ params }: HouseholdAIPageProps) {
  await requireSession();
  const { householdExternalId } = await params;
  const [status, recipeList] = await Promise.all([
    getHouseholdAIStatus(householdExternalId),
    getRecipeList(householdExternalId)
  ]);

  return (
    <HouseholdAISuggestions
      householdExternalId={householdExternalId}
      householdName={recipeList.household_name}
      initialStatus={status}
      recipes={recipeList.recipes}
    />
  );
}

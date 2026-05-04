import { ShoppingHistoryPanel } from "../../../../../../../components/shopping-history-panel";
import { getShoppingList, requireHouseholdAccess } from "../../../../../../../lib/server-auth";

type ShoppingHistoryPageProps = {
  params: Promise<{
    householdExternalId: string;
  }>;
};

export default async function HouseholdShoppingHistoryPage({
  params,
}: ShoppingHistoryPageProps) {
  const { householdExternalId } = await params;
  await requireHouseholdAccess(householdExternalId);
  const shoppingList = await getShoppingList(householdExternalId, { history_limit: 100 });

  return (
    <ShoppingHistoryPanel
      householdExternalId={householdExternalId}
      shoppingList={shoppingList}
    />
  );
}

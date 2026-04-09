import { ShoppingHistoryPanel } from "../../../../../../../components/shopping-history-panel";
import { getShoppingList, requireSession } from "../../../../../../../lib/server-auth";

type ShoppingHistoryPageProps = {
  params: Promise<{
    householdExternalId: string;
  }>;
};

export default async function HouseholdShoppingHistoryPage({
  params,
}: ShoppingHistoryPageProps) {
  await requireSession();
  const { householdExternalId } = await params;
  const shoppingList = await getShoppingList(householdExternalId, { history_limit: 100 });

  return (
    <ShoppingHistoryPanel
      householdExternalId={householdExternalId}
      shoppingList={shoppingList}
    />
  );
}

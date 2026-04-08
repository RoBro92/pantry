import { ShoppingListPanel } from "../../../../../../components/shopping-list-panel";
import { getShoppingList, requireSession } from "../../../../../../lib/server-auth";

type ShoppingListPageProps = {
  params: Promise<{
    householdExternalId: string;
  }>;
};

export default async function HouseholdShoppingListPage({
  params,
}: ShoppingListPageProps) {
  await requireSession();
  const { householdExternalId } = await params;
  const shoppingList = await getShoppingList(householdExternalId);

  return <ShoppingListPanel householdExternalId={householdExternalId} shoppingList={shoppingList} />;
}

import { ShoppingListPanel } from "../../../../../../components/shopping-list-panel";
import { getPantryOverview, getShoppingList, requireSession } from "../../../../../../lib/server-auth";

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
  const [shoppingList, pantryOverview] = await Promise.all([
    getShoppingList(householdExternalId),
    getPantryOverview(householdExternalId),
  ]);

  return (
    <ShoppingListPanel
      householdExternalId={householdExternalId}
      shoppingList={shoppingList}
      locations={pantryOverview.locations}
      canAdminister={pantryOverview.can_administer}
    />
  );
}

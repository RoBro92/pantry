import { ShoppingListPanel } from "../../../../../../components/shopping-list-panel";
import { getPantryOverview, getShoppingList, requireHouseholdAccess } from "../../../../../../lib/server-auth";

type ShoppingListPageProps = {
  params: Promise<{
    householdExternalId: string;
  }>;
};

export default async function HouseholdShoppingListPage({
  params,
}: ShoppingListPageProps) {
  const { householdExternalId } = await params;
  await requireHouseholdAccess(householdExternalId);
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

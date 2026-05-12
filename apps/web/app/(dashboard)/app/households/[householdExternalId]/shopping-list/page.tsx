import { ShoppingListPanel } from "../../../../../../components/shopping-list-panel";
import {
  getPantryLocationOptions,
  getShoppingList,
  requireHouseholdAccess
} from "../../../../../../lib/server-auth";

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
  const [shoppingList, pantryLocations] = await Promise.all([
    getShoppingList(householdExternalId),
    getPantryLocationOptions(householdExternalId),
  ]);

  return (
    <ShoppingListPanel
      householdExternalId={householdExternalId}
      shoppingList={shoppingList}
      locations={pantryLocations.locations}
      canAdminister={pantryLocations.can_administer}
    />
  );
}

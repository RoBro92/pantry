import Link from "next/link";
import { RecipeForm } from "../../../../../../../../components/recipe-form";
import {
  getPantryProductOptions,
  getRecipeDetail,
  requireHouseholdAccess
} from "../../../../../../../../lib/server-auth";

type RecipeEditPageProps = {
  params: Promise<{
    householdExternalId: string;
    recipeExternalId: string;
  }>;
};

export default async function RecipeEditPage({ params }: RecipeEditPageProps) {
  const { householdExternalId, recipeExternalId } = await params;
  await requireHouseholdAccess(householdExternalId);
  const [pantryProducts, recipeResponse] = await Promise.all([
    getPantryProductOptions(householdExternalId),
    getRecipeDetail(householdExternalId, recipeExternalId)
  ]);

  return (
    <div className="stack">
      <div className="page-actions">
        <Link
          href={`/app/households/${householdExternalId}/recipes/${recipeExternalId}`}
          className="secondary-link"
        >
          Back to recipe
        </Link>
      </div>
      <RecipeForm
        householdExternalId={householdExternalId}
        products={pantryProducts.products}
        mode="edit"
        initialValue={{
          recipeExternalId,
          title: recipeResponse.recipe.title,
          notes: recipeResponse.recipe.notes,
          ingredients: recipeResponse.recipe.ingredients.map((ingredient) => ({
            name: ingredient.name,
            quantity: ingredient.quantity,
            unit: ingredient.unit,
            note: ingredient.note,
            product_external_id: ingredient.product?.external_id ?? null
          }))
        }}
      />
    </div>
  );
}

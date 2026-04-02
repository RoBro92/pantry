import Link from "next/link";
import { RecipeForm } from "../../../../../../../../components/recipe-form";
import {
  getPantryOverview,
  getRecipeDetail,
  requireSession
} from "../../../../../../../../lib/server-auth";

type RecipeEditPageProps = {
  params: Promise<{
    householdExternalId: string;
    recipeExternalId: string;
  }>;
};

export default async function RecipeEditPage({ params }: RecipeEditPageProps) {
  await requireSession();
  const { householdExternalId, recipeExternalId } = await params;
  const [pantry, recipeResponse] = await Promise.all([
    getPantryOverview(householdExternalId),
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
        products={pantry.catalog_products}
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

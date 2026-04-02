import Link from "next/link";
import { RecipeForm } from "../../../../../../../components/recipe-form";
import { getPantryOverview, requireSession } from "../../../../../../../lib/server-auth";

type RecipeCreatePageProps = {
  params: Promise<{
    householdExternalId: string;
  }>;
};

export default async function RecipeCreatePage({ params }: RecipeCreatePageProps) {
  await requireSession();
  const { householdExternalId } = await params;
  const pantry = await getPantryOverview(householdExternalId);

  return (
    <div className="stack">
      <div className="page-actions">
        <Link href={`/app/households/${householdExternalId}/recipes`} className="secondary-link">
          Back to recipes
        </Link>
      </div>
      <RecipeForm
        householdExternalId={householdExternalId}
        products={pantry.catalog_products}
        mode="create"
      />
    </div>
  );
}

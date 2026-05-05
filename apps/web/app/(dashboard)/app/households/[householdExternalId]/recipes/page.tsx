import Link from "next/link";
import { CoverageBadge } from "../../../../../../components/coverage-badge";
import { StatusCard } from "../../../../../../components/status-card";
import { getRecipeList, requireHouseholdAccess } from "../../../../../../lib/server-auth";

type RecipeListPageProps = {
  params: Promise<{
    householdExternalId: string;
  }>;
};

export default async function HouseholdRecipeListPage({ params }: RecipeListPageProps) {
  const { householdExternalId } = await params;
  await requireHouseholdAccess(householdExternalId);
  const response = await getRecipeList(householdExternalId);

  return (
    <div className="stack">
      <section className="panel">
        <p className="eyebrow">Recipes</p>
        <h1>{response.household_name}</h1>
        <p>
          Manual recipe entry is live. Coverage is calculated against current pantry stock with
          deterministic ingredient-to-product matching and shopping gaps derived from missing
          quantities.
        </p>
        <div className="page-actions">
          <Link
            href={`/app/households/${response.household_external_id}`}
            className="secondary-link"
          >
            Back to pantry
          </Link>
          <Link
            href={`/app/households/${response.household_external_id}/recipes/new`}
            className="primary-link"
          >
            Create recipe
          </Link>
        </div>
      </section>

      <section className="status-grid">
        <StatusCard
          title="Recipes"
          value={String(response.recipes.length)}
          detail="Household-scoped recipes with pantry coverage summaries."
        />
        <StatusCard
          title="Fully Covered"
          value={String(
            response.recipes.filter((recipe) => recipe.pantry_coverage.status === "fully_covered")
              .length
          )}
          detail="Recipes that the current pantry can satisfy in full."
        />
        <StatusCard
          title="Partially Covered"
          value={String(
            response.recipes.filter(
              (recipe) => recipe.pantry_coverage.status === "partially_covered"
            ).length
          )}
          detail="Recipes with some pantry coverage but at least one remaining gap."
        />
        <StatusCard
          title="Missing"
          value={String(
            response.recipes.filter((recipe) => recipe.pantry_coverage.status === "missing").length
          )}
          detail="Recipes with no covered ingredients yet."
        />
      </section>

      <section className="panel">
        <p className="eyebrow">Recipe Library</p>
        {response.recipes.length === 0 ? (
          <div className="stack">
            <p>No recipes have been created for this household yet.</p>
            <p className="section-copy">
              Start with a recipe you cook often. Inventory coverage will stay useful even if some
              ingredients do not have a direct product match yet.
            </p>
            <div className="page-actions">
              <Link
                href={`/app/households/${response.household_external_id}/recipes/new`}
                className="primary-link"
              >
                Create the first recipe
              </Link>
              <Link
                href={`/app/households/${response.household_external_id}`}
                className="secondary-link"
              >
                Check inventory setup
              </Link>
            </div>
          </div>
        ) : (
          <div className="recipe-card-grid">
            {response.recipes.map((recipe) => (
              <article key={recipe.external_id} className="recipe-card">
                <div className="recipe-card-header">
                  <div>
                    <h2>{recipe.title}</h2>
                    <p>
                      {recipe.ingredient_count} ingredient
                      {recipe.ingredient_count === 1 ? "" : "s"} · updated{" "}
                      {new Date(recipe.updated_at).toLocaleString("en-GB", {
                        dateStyle: "medium",
                        timeStyle: "short"
                      })}
                    </p>
                  </div>
                  <CoverageBadge status={recipe.pantry_coverage.status} />
                </div>
                {recipe.notes ? <p>{recipe.notes}</p> : null}
                <div className="tag-row">
                  <span className="tag">
                    {recipe.pantry_coverage.fully_covered_count} fully covered
                  </span>
                  <span className="tag">
                    {recipe.pantry_coverage.partially_covered_count} partial
                  </span>
                  <span className="tag subtle-tag">
                    {recipe.pantry_coverage.shopping_gap_count} shopping gap
                    {recipe.pantry_coverage.shopping_gap_count === 1 ? "" : "s"}
                  </span>
                </div>
                <div className="page-actions">
                  <Link
                    href={`/app/households/${response.household_external_id}/recipes/${recipe.external_id}`}
                    className="primary-link"
                  >
                    View recipe
                  </Link>
                  <Link
                    href={`/app/households/${response.household_external_id}/recipes/${recipe.external_id}/edit`}
                    className="secondary-link"
                  >
                    Edit
                  </Link>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

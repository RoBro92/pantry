import Link from "next/link";
import { CoverageBadge } from "../../../../../../../components/coverage-badge";
import { RecipeShoppingGapActions } from "../../../../../../../components/recipe-shopping-gap-actions";
import { StatusCard } from "../../../../../../../components/status-card";
import { getRecipeDetail, requireSession } from "../../../../../../../lib/server-auth";

type RecipeDetailPageProps = {
  params: Promise<{
    householdExternalId: string;
    recipeExternalId: string;
  }>;
};

export default async function RecipeDetailPage({ params }: RecipeDetailPageProps) {
  await requireSession();
  const { householdExternalId, recipeExternalId } = await params;
  const response = await getRecipeDetail(householdExternalId, recipeExternalId);
  const recipe = response.recipe;

  return (
    <div className="stack">
      <section className="panel">
        <p className="eyebrow">Recipe Detail</p>
        <div className="page-actions">
          <div>
            <h1>{recipe.title}</h1>
            <p>
              {recipe.ingredient_count} ingredient{recipe.ingredient_count === 1 ? "" : "s"} ·
              created{" "}
              {new Date(recipe.created_at).toLocaleString("en-GB", {
                dateStyle: "medium",
                timeStyle: "short"
              })}
            </p>
          </div>
          <CoverageBadge status={recipe.pantry_coverage.status} />
        </div>
        {recipe.notes ? <p>{recipe.notes}</p> : null}
        <div className="page-actions">
          <Link href={`/app/households/${householdExternalId}/recipes`} className="secondary-link">
            Back to recipes
          </Link>
          <Link
            href={`/app/households/${householdExternalId}/recipes/${recipe.external_id}/edit`}
            className="primary-link"
          >
            Edit recipe
          </Link>
        </div>
      </section>

      <section className="status-grid">
        <StatusCard
          title="Fully Covered"
          value={String(recipe.pantry_coverage.fully_covered_count)}
          detail="Ingredients completely covered by pantry stock."
        />
        <StatusCard
          title="Partial"
          value={String(recipe.pantry_coverage.partially_covered_count)}
          detail="Ingredients with some stock available but not enough."
        />
        <StatusCard
          title="Missing"
          value={String(recipe.pantry_coverage.missing_count)}
          detail="Ingredients with no usable pantry coverage."
        />
        <StatusCard
          title="Shopping Gaps"
          value={String(recipe.pantry_coverage.shopping_gap_count)}
          detail="Derived missing quantities needed to make the recipe."
        />
      </section>

      <section className="panel">
        <p className="eyebrow">Ingredient Coverage</p>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Ingredient</th>
                <th>Linked product</th>
                <th>Needed</th>
                <th>Covered</th>
                <th>Missing</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {recipe.ingredients.map((ingredient) => (
                <tr key={ingredient.external_id}>
                  <td>
                    <strong>{ingredient.name}</strong>
                    {ingredient.note ? <div>{ingredient.note}</div> : null}
                  </td>
                  <td>
                    {ingredient.product ? (
                      <>
                        {ingredient.product.name}
                        <div>{ingredient.match_source === "manual" ? "Manual link" : "Auto match"}</div>
                      </>
                    ) : (
                      "No match"
                    )}
                  </td>
                  <td>
                    {ingredient.quantity} {ingredient.unit}
                  </td>
                  <td>
                    {ingredient.coverage.covered_quantity} {ingredient.unit}
                  </td>
                  <td>
                    {ingredient.coverage.missing_quantity} {ingredient.unit}
                    {ingredient.coverage.reason ? <div>{ingredient.coverage.reason}</div> : null}
                  </td>
                  <td>
                    <CoverageBadge status={ingredient.coverage.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="content-grid">
        <article className="panel">
          <p className="eyebrow">Shopping Gap</p>
          {recipe.shopping_gap_items.length === 0 ? (
            <p>No shopping gaps remain for this recipe.</p>
          ) : (
            <div className="stack">
              <RecipeShoppingGapActions
                householdExternalId={householdExternalId}
                recipeTitle={recipe.title}
                items={recipe.shopping_gap_items}
              />
              <ul className="detail-list">
                {recipe.shopping_gap_items.map((item) => (
                  <li key={`${item.label}-${item.unit}`}>
                    <strong>
                      {item.label} · {item.quantity} {item.unit}
                    </strong>
                    <span>
                      Derived from {item.ingredient_count} ingredient
                      {item.ingredient_count === 1 ? "" : "s"} that still need coverage.
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </article>

        <article className="panel">
          <p className="eyebrow">Recipe Metadata</p>
          <ul className="detail-list">
            <li>
              <strong>Source</strong>
              <span>{recipe.source_kind}</span>
            </li>
            {recipe.source_url ? (
              <li>
                <strong>Source URL</strong>
                <span>{recipe.source_url}</span>
              </li>
            ) : null}
            <li>
              <strong>Last updated</strong>
              <span>
                {new Date(recipe.updated_at).toLocaleString("en-GB", {
                  dateStyle: "medium",
                  timeStyle: "short"
                })}
              </span>
            </li>
            <li>
              <strong>Household role</strong>
              <span>{response.effective_role}</span>
            </li>
          </ul>
        </article>
      </section>
    </div>
  );
}

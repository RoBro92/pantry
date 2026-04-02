import Link from "next/link";
import { redirect } from "next/navigation";
import { AppShell } from "../../../components/app-shell";
import { getLocationAccess, getSession } from "../../../lib/server-auth";

type LocationRoutePageProps = {
  params: Promise<{
    locationRoute: string;
  }>;
};

export default async function LocationRoutePage({ params }: LocationRoutePageProps) {
  const { locationRoute } = await params;
  const session = await getSession();
  if (!session) {
    redirect(`/login?next=${encodeURIComponent(`/locations/${locationRoute}`)}`);
  }

  const access = await getLocationAccess(locationRoute);

  return (
    <AppShell session={session}>
      <div className="stack">
        <section className="panel">
          <p className="eyebrow">Location Link</p>
          <h1>
            {access.location.location_group_name} / {access.location.name}
          </h1>
          <p>
            This QR-safe link resolves server-side household access before it reveals location
            details or pantry navigation.
          </p>
          <div className="page-actions">
            <Link href={access.pantry_path} className="primary-link">
              Open filtered pantry
            </Link>
            <Link
              href={`/app/households/${access.household_external_id}`}
              className="secondary-link"
            >
              Open household
            </Link>
          </div>
        </section>

        <section className="status-grid">
          <article className="status-card">
            <p className="eyebrow">Household</p>
            <h2>{access.household_name}</h2>
            <p>{access.effective_role}</p>
          </article>
          <article className="status-card">
            <p className="eyebrow">Products</p>
            <h2>{access.active_product_count}</h2>
            <p>Distinct active products currently stored in this location.</p>
          </article>
          <article className="status-card">
            <p className="eyebrow">Lots</p>
            <h2>{access.active_lot_count}</h2>
            <p>Active lots currently stored in this location.</p>
          </article>
        </section>

        <section className="panel">
          <p className="eyebrow">Current Stock</p>
          {access.stock_lots.length === 0 ? (
            <p>No active stock lots are currently stored in this location.</p>
          ) : (
            <ul className="detail-list">
              {access.stock_lots.map((lot) => (
                <li key={lot.external_id}>
                  <strong>
                    {lot.product_name} · {lot.quantity} {lot.unit}
                  </strong>
                  <span>
                    {lot.expires_on ? `Expires ${lot.expires_on}` : "No expiry"} · {lot.note ?? "No note"}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </AppShell>
  );
}

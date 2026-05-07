import Link from "next/link";
import QRCode from "qrcode";
import type { PantryLocationSummary } from "../lib/api-types";

type LocationQRCodeCardProps = {
  location: PantryLocationSummary;
};

export async function LocationQRCodeCard({ location }: LocationQRCodeCardProps) {
  if (!location.browser_url || !location.browser_path) {
    return (
      <article className="location-link-card panel" data-testid={`location-link-card-${location.external_id}`}>
        <p className="eyebrow">Location Link</p>
        <h2>
          {location.location_group_name} / {location.name}
        </h2>
        <p>Public browser URL is not available for this location yet.</p>
      </article>
    );
  }

  const svg = await QRCode.toString(location.browser_url, {
    type: "svg",
    margin: 1,
    width: 180
  });

  return (
    <article className="location-link-card panel" data-testid={`location-link-card-${location.external_id}`}>
      <p className="eyebrow">Location QR</p>
      <h2>
        {location.location_group_name} / {location.name}
      </h2>
      <div
        className="qr-frame"
        dangerouslySetInnerHTML={{ __html: svg }}
      />
      <p className="section-copy">Opens the signed-in view for this storage location.</p>
      <div className="page-actions">
        <Link href={location.browser_path} className="secondary-link">
          Open link
        </Link>
      </div>
    </article>
  );
}

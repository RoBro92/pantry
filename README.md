# Pantry

Pantry is a self hosted household inventory and meal management application for tracking food, reducing waste, and keeping day to day kitchen workflows clear. It was built as a means to an end as i found the existing offerings such as Grocy were too bloated with features I didn't need. It was also missing some key features i wanted to make the day to day use of the program not be a chore. Think "Remove 20g of cheese for a sandwich" So Pantry was created to provide a simple interface with support for multiple households. 

## Features

- Pantry inventory with Rooms, storage locations, product-first browsing, condensed stock-lot actions, and expiry tracking
- Optional Open Food Facts product enrichment with compact barcode lookup, duplicate-aware product creation, and user-owned product identity
- Shopping lists with active, awaiting-purchase, merge, return, export, and reconciliation flows
- Password change in user settings plus optional self-service password reset by email when SMTP is configured, tested, and enabled
- Recipe management with pantry insights
- QR location access with quick add/remove flows
- Diagnostics, update visibility, and manual update guidance
- Native backup export plus guarded restore foundations
- Optional AI-powered suggestions for recipes based on dietary requirements for users with suggestions on additional purchase
- Guided first run setup and login flow, including restore from backup

## Quick Start

```bash
curl -fsSL https://raw.githubusercontent.com/RoBro92/pantry/main/infra/scripts/install-pantry.sh | bash
```

The installer prepares Docker, writes environment defaults, pulls the release assets, runs migrations, and starts the stack.

## Manual Installation

```bash
git clone https://github.com/RoBro92/pantry.git
cd pantry

cp infra/env/pantry.env.example .env

docker compose -f infra/compose/pantry.yml up -d
docker compose exec api alembic upgrade head
```

## First Run

Open:

```text
http://<your-server-ip>:3000
```
Pantry supports two first run paths:

- `Fresh install`
- `Restore from backup`

Restore currently accepts Pantry native full instance JSON backup bundles only. Uploaded restore files are validated, staged in quarantine, and never executed as code.

## Pantry Workflow

The household pantry page is built as a compact product browser with inline search and filters. Search by product name, alias, or barcode, switch between table and list views, expand a product only when you need stock-lot detail, and use `Add product` to create a product and its first stock lot in one flow.

When adding a product, Pantry supports:

- duplicate detection before you commit, including exact barcode matching and name-similarity checks
- optional Open Food Facts preview and enrichment linking
- manual ingredient tags that stay user-owned
- barcode entry with USB-scanner friendly input, inline lookup, and browser camera hooks where supported
- clean duplicate-product detection that routes directly into adding another stock lot instead of creating a second product when Pantry already knows the item

Open Food Facts data is advisory enrichment only. Pantry keeps the product name, aliases, and stock identity as user-owned records, while attached enrichment survives backups and restores for later UI, filtering, and AI use.

## Accounts And Access

Logged-in users can change their own password from Settings. Self-service password reset from the login page stays hidden unless a platform admin has configured SMTP, run a successful SMTP test, and explicitly enabled password reset emails for the instance.

Accounts without an email address can still sign in normally, but they cannot use self-service password reset and will need an admin-led reset instead.

## Updating Pantry

```bash
./infra/scripts/update-pantry.sh
```

Pantry does not self-update. Platform admins can review the current version, latest published release metadata, changelog summaries, breaking change notes, and operator commands from the admin `Updates` page.

## Backups And Recovery

Platform admins can use the admin `Backups` page to:

- export a full instance Pantry backup bundle
- export a household-specific Pantry bundle for retention or inspection
- upload and validate a full instance restore bundle before applying it deliberately

Current restore support is limited to Pantry backup bundle v1 JSON files from the same schema revision.

## Configuration

Edit:

```text
infra/env/pantry.env.example
```

Key options include:

- `WEB_APP_URL`
- `API_BASE_URL`
- `NEXT_PUBLIC_API_BASE_URL`
- `PUBLIC_BROWSER_BASE_URL`
- database credentials
- optional AI provider settings
- optional SMTP settings

## Validation And Local Development

See:

- [docs/CONTRIBUTING.md](/Users/robinbrown/Documents/GitHub/pantry/docs/CONTRIBUTING.md)
- [docs/DEPLOYMENT.md](/Users/robinbrown/Documents/GitHub/pantry/docs/DEPLOYMENT.md)
- [docs/ARCHITECTURE.md](/Users/robinbrown/Documents/GitHub/pantry/docs/ARCHITECTURE.md)
- [docs/MILESTONES.md](/Users/robinbrown/Documents/GitHub/pantry/docs/MILESTONES.md)
- [docs/TEST_STRATEGY.md](/Users/robinbrown/Documents/GitHub/pantry/docs/TEST_STRATEGY.md)

## Troubleshooting

```bash
docker compose logs -f
docker compose restart
./infra/scripts/healthcheck-pantry.sh
```

## Versioning

The running version is defined by the `VERSION` file and surfaced across the app, diagnostics, and updates UI.

See also:

- [docs/VERSIONING.md](/Users/robinbrown/Documents/GitHub/pantry/docs/VERSIONING.md)
- [docs/SECURITY.md](/Users/robinbrown/Documents/GitHub/pantry/docs/SECURITY.md)

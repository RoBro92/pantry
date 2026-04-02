# Domain Model

## Entities

### User

Represents a human account that can belong to one or more households. Users may also hold platform-level capabilities.
Current implementation notes:

- Uses an opaque external ID for tenant-facing references.
- Stores normalized email, password hash, active flag, and optional platform role.
- Tracks `last_login_at` for basic session activity visibility.

### Household

Primary tenant boundary for pantry, recipe, shopping, import, and most settings data.
Current implementation notes:

- Uses an opaque external ID for tenant-facing routes and API payloads.
- The initial model only stores identity metadata and timestamps.

### Membership

Joins a `User` to a `Household` and carries household-scoped role and lifecycle state.
Current implementation notes:

- Unique per user-household pair.
- Stores an active flag for future lifecycle changes.
- Carries the household-scoped role assignment.

### Role

Represents access level. Current role set is `platform_admin`, `household_admin`, and `household_user`.
Current implementation notes:

- Seeded by the first Alembic migration.
- Supports both platform-scoped and household-scoped assignments.

### LocationGroup

Logical grouping of storage areas inside a household, such as kitchen, garage, or basement.
Current implementation notes:

- Uses an opaque external ID for tenant-facing references.
- Name uniqueness is enforced per household through normalized server-side matching.

### Location

Concrete pantry location within a group, such as top shelf, freezer drawer, or spice rack. QR codes deep-link here.
Current implementation notes:

- Uses an opaque external ID for tenant-facing references.
- Belongs to one `LocationGroup` and one `Household`.
- Name uniqueness is enforced within the containing group through normalized server-side matching.

### Product

Normalized product definition used inside a household, potentially linked to aliases and barcodes.
Current implementation notes:

- Uses an opaque external ID for tenant-facing references.
- Stores a canonical name and default unit.
- Canonical names cannot collide with other product names or aliases inside the same household.

### ProductAlias

Alternate product names or import-normalization labels that map back to a `Product`.
Current implementation notes:

- Uses an opaque external ID for tenant-facing references.
- Alias matching is normalized deterministically server-side.
- Alias names are unique per household to avoid ambiguous product resolution.

### Barcode

Barcode identifiers associated with a product for scanning and import matching.
Current implementation notes:

- Uses an opaque external ID for tenant-facing references.
- Barcode values are normalized deterministically server-side before storage and matching.
- Barcode values are unique per household.

### StockLot

Specific held quantity of a product in a location, with optional purchase, expiry, and note metadata.
Current implementation notes:

- Uses an opaque external ID for tenant-facing references.
- Active pantry totals are derived from stock lots rather than replacing them with summary rows.
- Full-lot moves preserve lot identity; partial moves split into a new lot with copied metadata.
- Fully removed lots are retained with zero quantity and a `depleted_at` timestamp so audit trails and lot identity remain coherent.

### Recipe

Structured recipe owned by a household or imported for a household.
Current implementation notes:

- Uses an opaque external ID for tenant-facing references.
- Supports manual recipe entry with household-scoped title, notes, and source metadata.
- Pantry coverage and shopping gaps are derived from linked ingredients against active stock lots.

### RecipeIngredient

Ingredient line linked to a recipe, with optional mapping to a product.
Current implementation notes:

- Uses an opaque external ID for tenant-facing references.
- Stores quantity, normalized unit, optional note, and stable order within the recipe.
- Supports explicit pantry-product links plus deterministic server-side auto-matching by normalized product or alias name.
- Coverage is calculated in ingredient order so repeated ingredients do not over-count the same pantry stock.

### RecipeURLImport

Persisted household-scoped request to import a recipe from a URL.
Current implementation notes:

- Uses an opaque external ID for tenant-facing references.
- Stores the original URL, a normalized URL, capture status, and requesting actor.
- Current v1 behavior only captures import requests as a clean foundation for later parsing and worker-backed processing.

### ImportJob

Tracks the lifecycle of an import run, including source, status, timing, and review outcome.
Current implementation notes:

- Uses an opaque external ID for tenant-facing references.
- Belongs to one household and one requesting actor when available.
- Stores source type, lifecycle status, optional occurred-on date, parser kind, failure detail, and line-status counts.
- Review-ready imports remain distinct from confirmed imports; confirmation is the only point that writes pantry stock.

### ImportSourceFile

Metadata about an uploaded file tied to an import job. The file is untrusted input.
Current implementation notes:

- Uses an opaque external ID for tenant-facing references.
- Stores upload metadata such as original filename, detected content type, file size, checksum, and relative storage path.
- Tracks application-level validation and scan status so future quarantine or malware-scanning work has a clean persistence hook.

### ImportLine

Reviewable parsed line or record extracted from an import source.
Current implementation notes:

- Uses an opaque external ID for tenant-facing references.
- Stores raw label, normalized label, quantity, unit, optional barcode, optional notes, and line-level status.
- Keeps current matched product separate from suggested product so manual review can override deterministic matching without losing the original suggestion.
- Can link to a confirmed `StockLot` once the reviewed import is written into pantry inventory.

### ShoppingList

Household-scoped list of items to buy.

### ShoppingListItem

Line item within a shopping list, optionally linked to a product.

### AuditEvent

Durable record of a domain-significant action for accountability and traceability.
Current implementation notes:

- Pantry location, product, add, remove, and move actions now emit audit events.
- Audit payloads keep operational logs distinct from business accountability records.

### AIProviderConfig

Instance- or household-scoped configuration for AI providers, stored and redacted carefully.
Current implementation notes:

- The initial implementation stores one instance-scoped configuration and leaves room for future household overrides through the same model shape.
- Supports `ollama` and `openai_compatible` provider types.
- Stores base URL, default model, enabled state, provider health metadata, and encrypted secret material when needed.
- API responses expose only redacted state such as `has_api_key`; raw provider secrets are not returned.

### FeatureFlag

Runtime feature gating at platform, deployment-mode, or household scope.

### UsageCounter

Metering record for rate limits, plan enforcement, or SaaS usage analysis.

## Relationship Notes

- `Household` is the primary owner of `LocationGroup`, `Location`, `Product`, `StockLot`, `Recipe`, `ShoppingList`, and import data.
- `AIProviderConfig` currently resolves at instance scope first for v1 and is shaped so household override resolution can layer in later.
- `Membership` mediates household access.
- `AuditEvent` references actors and targets without becoming a substitute for business tables.
- `FeatureFlag` and `UsageCounter` are needed early in the model so SaaS later does not require structural rewrites.
- The current auth foundation does not persist server-side sessions as a domain entity; a signed session cookie carries the authenticated user reference.
- `ImportSourceFile`, `ImportLine`, and confirmed `StockLot` records stay explicitly linked but do not collapse into a single table, preserving reviewability and audit traceability.

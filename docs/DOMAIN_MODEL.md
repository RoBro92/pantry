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

### RecipeIngredient

Ingredient line linked to a recipe, with optional mapping to a product.

### ImportJob

Tracks the lifecycle of an import run, including source, status, timing, and review outcome.

### ImportSourceFile

Metadata about an uploaded file tied to an import job. The file is untrusted input.

### ImportLine

Reviewable parsed line or record extracted from an import source.

### ShoppingList

Household-scoped list of items to buy.

### ShoppingListItem

Line item within a shopping list, optionally linked to a product.

### AuditEvent

Durable record of a domain-significant action for accountability and traceability.
Current implementation notes:

- Pantry location, product, add, remove, and move actions now emit audit events.
- Audit payloads keep operational logs distinct from business accountability records.

### LLMProviderConfig

Household- or platform-scoped configuration for AI providers, stored and redacted carefully.

### FeatureFlag

Runtime feature gating at platform, deployment-mode, or household scope.

### UsageCounter

Metering record for rate limits, plan enforcement, or SaaS usage analysis.

## Relationship Notes

- `Household` is the primary owner of `LocationGroup`, `Location`, `Product`, `StockLot`, `Recipe`, `ShoppingList`, and import data.
- `Membership` mediates household access.
- `AuditEvent` references actors and targets without becoming a substitute for business tables.
- `FeatureFlag` and `UsageCounter` are needed early in the model so SaaS later does not require structural rewrites.
- The current auth foundation does not persist server-side sessions as a domain entity; a signed session cookie carries the authenticated user reference.

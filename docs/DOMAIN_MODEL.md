# Domain Model

## Entities

### User

Represents a human account that can belong to one or more households. Users may also hold platform-level capabilities.

### Household

Primary tenant boundary for pantry, recipe, shopping, import, and most settings data.

### Membership

Joins a `User` to a `Household` and carries household-scoped role and lifecycle state.

### Role

Represents access level. Current role set is `platform_admin`, `household_admin`, and `household_user`.

### LocationGroup

Logical grouping of storage areas inside a household, such as kitchen, garage, or basement.

### Location

Concrete pantry location within a group, such as top shelf, freezer drawer, or spice rack. QR codes deep-link here.

### Product

Normalized product definition used inside a household, potentially linked to aliases and barcodes.

### ProductAlias

Alternate product names or import-normalization labels that map back to a `Product`.

### Barcode

Barcode identifiers associated with a product for scanning and import matching.

### StockLot

Specific held quantity of a product in a location, with optional purchase, expiry, and note metadata.

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


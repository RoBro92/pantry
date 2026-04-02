export const deploymentModes = [
  "self_hosted",
  "demo",
  "saas_free",
  "saas_supporter"
] as const;

export type DeploymentMode = (typeof deploymentModes)[number];

export const pantryRoles = [
  "platform_admin",
  "household_admin",
  "household_user"
] as const;

export type PantryRole = (typeof pantryRoles)[number];

export const domainEntities = [
  "User",
  "Household",
  "Membership",
  "Role",
  "LocationGroup",
  "Location",
  "Product",
  "ProductAlias",
  "Barcode",
  "StockLot",
  "Recipe",
  "RecipeIngredient",
  "ImportJob",
  "ImportSourceFile",
  "ImportLine",
  "ShoppingList",
  "ShoppingListItem",
  "AuditEvent",
  "LLMProviderConfig",
  "FeatureFlag",
  "UsageCounter"
] as const;

export type DomainEntityName = (typeof domainEntities)[number];

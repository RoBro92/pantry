export type SessionMembership = {
  external_id: string;
  household_external_id: string;
  household_name: string;
  role: string;
  is_active: boolean;
};

export type SessionResponse = {
  authenticated: true;
  user: {
    external_id: string;
    email: string;
    display_name: string | null;
    is_active: boolean;
    platform_role: string | null;
  };
  memberships: SessionMembership[];
};

export type AdminOverview = {
  user_count: number;
  platform_admin_count: number;
  household_count: number;
  membership_count: number;
};

export type AdminUserSummary = {
  external_id: string;
  email: string;
  display_name: string | null;
  is_active: boolean;
  platform_role: string | null;
  membership_count: number;
};

export type AdminHouseholdSummary = {
  external_id: string;
  name: string;
  membership_count: number;
};

export type PantryLocationGroupSummary = {
  external_id: string;
  name: string;
  location_count: number;
};

export type PantryLocationSummary = {
  external_id: string;
  name: string;
  location_group_external_id: string;
  location_group_name: string;
};

export type PantryProductLocationSummary = {
  location_external_id: string;
  location_name: string;
  location_group_name: string;
  total_quantity: string;
  lot_count: number;
};

export type PantryProductSummary = {
  product_external_id: string;
  product_name: string;
  unit: string;
  total_quantity: string;
  lot_count: number;
  aliases: string[];
  barcodes: string[];
  locations: PantryProductLocationSummary[];
};

export type PantryCatalogProductSummary = {
  external_id: string;
  name: string;
  default_unit: string;
  aliases: string[];
  barcodes: string[];
};

export type PantryStockLotSummary = {
  external_id: string;
  product_external_id: string;
  product_name: string;
  location_external_id: string;
  location_name: string;
  location_group_name: string;
  quantity: string;
  unit: string;
  note: string | null;
  purchased_on: string | null;
  expires_on: string | null;
  is_near_expiry: boolean;
};

export type PantryAuditEventSummary = {
  external_id: string;
  action: string;
  summary: string;
  actor_display: string | null;
  target_type: string;
  target_external_id: string;
  occurred_at: string;
};

export type PantryOverview = {
  household_external_id: string;
  household_name: string;
  effective_role: string;
  can_administer: boolean;
  filters: {
    q: string | null;
    location_group_external_id: string | null;
    location_external_id: string | null;
  };
  counts: {
    location_group_count: number;
    location_count: number;
    product_count: number;
    active_lot_count: number;
    near_expiry_lot_count: number;
  };
  location_groups: PantryLocationGroupSummary[];
  locations: PantryLocationSummary[];
  catalog_products: PantryCatalogProductSummary[];
  products: PantryProductSummary[];
  stock_lots: PantryStockLotSummary[];
  recent_events: PantryAuditEventSummary[];
};

export type NearExpiryResponse = {
  household_external_id: string;
  days: number;
  lots: PantryStockLotSummary[];
};

export type RecipeCoverageSummary = {
  status: "fully_covered" | "partially_covered" | "missing";
  fully_covered_count: number;
  partially_covered_count: number;
  missing_count: number;
  shopping_gap_count: number;
};

export type RecipeLinkedProductSummary = {
  external_id: string;
  name: string;
  default_unit: string;
};

export type RecipeIngredientCoverageSummary = {
  status: "fully_covered" | "partially_covered" | "missing";
  pantry_available_quantity: string;
  covered_quantity: string;
  missing_quantity: string;
  comparison_unit: string | null;
  reason: string | null;
};

export type RecipeIngredientSummary = {
  external_id: string;
  position: number;
  name: string;
  quantity: string;
  unit: string;
  note: string | null;
  match_source: "manual" | "automatic" | "none";
  product: RecipeLinkedProductSummary | null;
  coverage: RecipeIngredientCoverageSummary;
};

export type RecipeShoppingGapItem = {
  label: string;
  quantity: string;
  unit: string;
  product_external_id: string | null;
  product_name: string | null;
  ingredient_count: number;
};

export type RecipeListItem = {
  external_id: string;
  title: string;
  notes: string | null;
  source_kind: string;
  source_url: string | null;
  ingredient_count: number;
  pantry_coverage: RecipeCoverageSummary;
  updated_at: string;
};

export type RecipeDetail = {
  external_id: string;
  title: string;
  notes: string | null;
  source_kind: string;
  source_url: string | null;
  ingredient_count: number;
  pantry_coverage: RecipeCoverageSummary;
  ingredients: RecipeIngredientSummary[];
  shopping_gap_items: RecipeShoppingGapItem[];
  created_at: string;
  updated_at: string;
};

export type RecipeListResponse = {
  household_external_id: string;
  household_name: string;
  effective_role: string;
  can_administer: boolean;
  recipes: RecipeListItem[];
};

export type RecipeDetailResponse = {
  household_external_id: string;
  household_name: string;
  effective_role: string;
  can_administer: boolean;
  recipe: RecipeDetail;
};

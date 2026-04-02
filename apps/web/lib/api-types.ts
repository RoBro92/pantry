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


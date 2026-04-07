export type HouseholdRole = "household_admin" | "household_user";
export type PlatformRole = "platform_admin";

type RoleLabelOptions = {
  detailed?: boolean;
};

export function getHouseholdRoleLabel(
  role: HouseholdRole | string,
  options?: RoleLabelOptions
): string {
  if (role === "household_admin") {
    return options?.detailed ? "Household Admin" : "Admin";
  }
  if (role === "household_user") {
    return "User";
  }
  return role;
}

export function getPlatformRoleLabel(
  role: PlatformRole | string | null | undefined,
  options?: RoleLabelOptions
): string {
  if (role === "platform_admin") {
    return options?.detailed ? "Platform Admin" : "Admin";
  }
  if (!role) {
    return "None";
  }
  return role;
}

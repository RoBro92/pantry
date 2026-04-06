export type HouseholdRole = "household_admin" | "household_user";

export function getHouseholdRoleLabel(role: HouseholdRole | string): string {
  if (role === "household_admin") {
    return "Admin";
  }
  if (role === "household_user") {
    return "User";
  }
  return role;
}

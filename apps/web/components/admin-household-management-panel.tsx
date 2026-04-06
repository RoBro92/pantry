"use client";

import { FormEvent, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import type { AdminHouseholdSummary, AdminUserSummary } from "../lib/api-types";
import { postToApi } from "../lib/client-api";
import { getHouseholdRoleLabel } from "../lib/role-labels";

type AdminHouseholdManagementPanelProps = {
  households: AdminHouseholdSummary[];
  users: AdminUserSummary[];
};

export function AdminHouseholdManagementPanel({
  households,
  users,
}: AdminHouseholdManagementPanelProps) {
  const router = useRouter();
  const [householdError, setHouseholdError] = useState<string | null>(null);
  const [householdSuccess, setHouseholdSuccess] = useState<string | null>(null);
  const [householdPending, setHouseholdPending] = useState(false);
  const [membershipError, setMembershipError] = useState<string | null>(null);
  const [membershipSuccess, setMembershipSuccess] = useState<string | null>(null);
  const [membershipPending, setMembershipPending] = useState(false);
  const [selectedHousehold, setSelectedHousehold] = useState(households[0]?.external_id ?? "");
  const [selectedUser, setSelectedUser] = useState(users[0]?.external_id ?? "");
  const selectedHouseholdSummary = useMemo(
    () => households.find((household) => household.external_id === selectedHousehold) ?? null,
    [households, selectedHousehold],
  );

  async function handleCreateHousehold(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setHouseholdError(null);
    setHouseholdSuccess(null);
    setHouseholdPending(true);

    const form = event.currentTarget;
    const formData = new FormData(form);
    try {
      const created = await postToApi<AdminHouseholdSummary>("/api/platform-admin/households", {
        name: String(formData.get("name") ?? ""),
      });
      setHouseholdSuccess(`Created household ${created.name}.`);
      form.reset();
      router.refresh();
      setHouseholdPending(false);
    } catch (submissionError) {
      setHouseholdError(
        submissionError instanceof Error ? submissionError.message : "Household creation failed.",
      );
      setHouseholdPending(false);
    }
  }

  async function handleAssignMembership(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMembershipError(null);
    setMembershipSuccess(null);
    setMembershipPending(true);

    const formData = new FormData(event.currentTarget);
    const householdExternalId = String(formData.get("household_external_id") ?? "");
    const userExternalId = String(formData.get("user_external_id") ?? "");
    const role = String(formData.get("role") ?? "");

    try {
      const created = await postToApi<{ email: string; role: string }>(
        `/api/platform-admin/households/${householdExternalId}/memberships`,
        {
          user_external_id: userExternalId,
          role,
        },
      );
      setMembershipSuccess(`Assigned ${created.email} as ${getHouseholdRoleLabel(created.role)}.`);
      router.refresh();
      setMembershipPending(false);
    } catch (submissionError) {
      setMembershipError(
        submissionError instanceof Error ? submissionError.message : "Membership update failed.",
      );
      setMembershipPending(false);
    }
  }

  return (
    <div className="content-grid">
      <form className="panel" onSubmit={handleCreateHousehold} data-testid="admin-create-household-form">
        <p className="eyebrow">Households</p>
        <h2>Create household</h2>
        <p className="section-copy">
          Start with a clear household name, then assign one or more users to it.
        </p>
        <label className="field">
          <span>Household name</span>
          <input name="name" placeholder="Brown family" required />
        </label>
        {householdError ? <p className="error-text">{householdError}</p> : null}
        {householdSuccess ? <p className="status-note">{householdSuccess}</p> : null}
        <button type="submit" className="primary-button" disabled={householdPending}>
          {householdPending ? "Creating..." : "Create household"}
        </button>
      </form>

      <form className="panel" onSubmit={handleAssignMembership} data-testid="admin-assign-membership-form">
        <p className="eyebrow">Memberships</p>
        <h2>Assign user to household</h2>
        {users.length === 0 ? (
          <p className="section-copy">
            Create at least one user first. Membership assignment stays disabled until a user
            exists.
          </p>
        ) : null}
        {households.length === 0 ? (
          <p className="section-copy">
            Create a household first. Membership assignment stays disabled until a household exists.
          </p>
        ) : null}
        <div className="recipe-form-grid">
          <label className="field">
            <span>Household</span>
            <select
              name="household_external_id"
              value={selectedHousehold}
              onChange={(event) => setSelectedHousehold(event.target.value)}
              required
            >
              <option value="">Select a household</option>
              {households.map((household) => (
                <option key={household.external_id} value={household.external_id}>
                  {household.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>User</span>
            <select
              name="user_external_id"
              value={selectedUser}
              onChange={(event) => setSelectedUser(event.target.value)}
              required
            >
              <option value="">Select a user</option>
              {users.map((user) => (
                <option key={user.external_id} value={user.external_id}>
                  {user.display_name ?? user.email} ({user.email})
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Role</span>
            <select name="role" defaultValue="household_admin" required>
              <option value="household_admin">{getHouseholdRoleLabel("household_admin")}</option>
              <option value="household_user">{getHouseholdRoleLabel("household_user")}</option>
            </select>
          </label>
        </div>
        {selectedHouseholdSummary ? (
          <p className="section-copy">
            Current members:{" "}
            {selectedHouseholdSummary.memberships.length === 0
              ? "none yet"
              : selectedHouseholdSummary.memberships
                  .map(
                    (membership) =>
                      `${membership.display_name ?? membership.email} (${getHouseholdRoleLabel(membership.role)})`,
                  )
                  .join(", ")}
          </p>
        ) : null}
        {membershipError ? <p className="error-text">{membershipError}</p> : null}
        {membershipSuccess ? <p className="status-note">{membershipSuccess}</p> : null}
        <button
          type="submit"
          className="primary-button"
          disabled={membershipPending || households.length === 0 || users.length === 0}
        >
          {membershipPending ? "Saving..." : "Assign membership"}
        </button>
      </form>
    </div>
  );
}

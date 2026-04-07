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
  const [maintenanceError, setMaintenanceError] = useState<string | null>(null);
  const [maintenanceSuccess, setMaintenanceSuccess] = useState<string | null>(null);
  const [maintenancePending, setMaintenancePending] = useState(false);
  const [deleteConfirmation, setDeleteConfirmation] = useState("");
  const [acknowledgeLastHousehold, setAcknowledgeLastHousehold] = useState(false);
  const [selectedHousehold, setSelectedHousehold] = useState(households[0]?.external_id ?? "");
  const [selectedUser, setSelectedUser] = useState(users[0]?.external_id ?? "");
  const selectedHouseholdSummary = useMemo(
    () => households.find((household) => household.external_id === selectedHousehold) ?? null,
    [households, selectedHousehold],
  );
  const isLastHousehold = households.length === 1;

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

  async function handleRemoveMembership(membershipExternalId: string, displayLabel: string) {
    const confirmed = window.confirm(
      `Remove ${displayLabel} from ${selectedHouseholdSummary?.name ?? "this household"}?`,
    );
    if (!confirmed || !selectedHouseholdSummary) {
      return;
    }

    setMaintenanceError(null);
    setMaintenanceSuccess(null);
    setMaintenancePending(true);
    try {
      const response = await postToApi<{ message: string }>(
        `/api/platform-admin/households/${selectedHouseholdSummary.external_id}/memberships/${membershipExternalId}/remove`,
        {},
      );
      setMaintenanceSuccess(response.message);
      router.refresh();
    } catch (requestError) {
      setMaintenanceError(
        requestError instanceof Error ? requestError.message : "Membership removal failed.",
      );
    } finally {
      setMaintenancePending(false);
    }
  }

  async function handleDeleteHousehold(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedHouseholdSummary) {
      return;
    }

    setMaintenanceError(null);
    setMaintenanceSuccess(null);
    setMaintenancePending(true);
    try {
      const response = await postToApi<{ message: string }>(
        `/api/platform-admin/households/${selectedHouseholdSummary.external_id}/delete`,
        {
          confirm_household_name: deleteConfirmation,
          acknowledge_last_household_deletion: acknowledgeLastHousehold,
        },
      );
      setMaintenanceSuccess(response.message);
      setDeleteConfirmation("");
      setAcknowledgeLastHousehold(false);
      router.refresh();
    } catch (requestError) {
      setMaintenanceError(
        requestError instanceof Error ? requestError.message : "Household deletion failed.",
      );
    } finally {
      setMaintenancePending(false);
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

      <form
        className="panel"
        onSubmit={handleDeleteHousehold}
        data-testid="admin-household-maintenance-form"
      >
        <p className="eyebrow">Maintenance</p>
        <h2>Manage memberships and deletion</h2>
        {households.length === 0 ? (
          <p className="section-copy">Create a household before using these controls.</p>
        ) : (
          <div className="stack">
            <label className="field">
              <span>Household</span>
              <select
                name="maintenance_household_external_id"
                value={selectedHousehold}
                onChange={(event) => {
                  setSelectedHousehold(event.target.value);
                  setDeleteConfirmation("");
                  setAcknowledgeLastHousehold(false);
                }}
              >
                {households.map((household) => (
                  <option key={household.external_id} value={household.external_id}>
                    {household.name}
                  </option>
                ))}
              </select>
            </label>

            {selectedHouseholdSummary ? (
              <div className="stack">
                <div className="warning-callout">
                  <strong>Membership removal safeguards</strong>
                  <p>
                    Pantry will block removals that would leave the household without a household
                    admin.
                  </p>
                </div>
                <div className="stack">
                  {selectedHouseholdSummary.memberships.length === 0 ? (
                    <p className="section-copy">No memberships to remove.</p>
                  ) : (
                    selectedHouseholdSummary.memberships.map((membership) => (
                      <div key={membership.membership_external_id} className="table-member-row">
                        <div>
                          <strong>{membership.display_name ?? membership.email}</strong>
                          <div className="helper-text">
                            {membership.email} · {getHouseholdRoleLabel(membership.role)}
                          </div>
                        </div>
                        <button
                          type="button"
                          className="ghost-button"
                          onClick={() =>
                            void handleRemoveMembership(
                              membership.membership_external_id,
                              membership.display_name ?? membership.email,
                            )
                          }
                          disabled={maintenancePending}
                        >
                          Remove
                        </button>
                      </div>
                    ))
                  )}
                </div>

                <div className="warning-callout">
                  <strong>Delete household</strong>
                  <p>
                    This removes pantry, recipe, import, membership, AI, and audit records for the
                    selected household.
                  </p>
                </div>
                <label className="field">
                  <span>Type the household name to confirm deletion</span>
                  <input
                    value={deleteConfirmation}
                    onChange={(event) => setDeleteConfirmation(event.target.value)}
                    placeholder={selectedHouseholdSummary.name}
                  />
                </label>
                {isLastHousehold ? (
                  <label className="checkbox-row">
                    <input
                      type="checkbox"
                      checked={acknowledgeLastHousehold}
                      onChange={(event) => setAcknowledgeLastHousehold(event.target.checked)}
                    />
                    <span>I understand this is the last household in the installation.</span>
                  </label>
                ) : null}
              </div>
            ) : null}
          </div>
        )}
        {maintenanceError ? <p className="error-text">{maintenanceError}</p> : null}
        {maintenanceSuccess ? <p className="status-note">{maintenanceSuccess}</p> : null}
        <button
          type="submit"
          className="primary-button"
          disabled={
            maintenancePending ||
            !selectedHouseholdSummary ||
            deleteConfirmation !== selectedHouseholdSummary.name ||
            (isLastHousehold && !acknowledgeLastHousehold)
          }
        >
          {maintenancePending ? "Working..." : "Delete household"}
        </button>
      </form>
    </div>
  );
}

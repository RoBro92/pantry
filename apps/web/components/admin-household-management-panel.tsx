"use client";

import Link from "next/link";
import { FormEvent, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import type { AdminHouseholdSummary, AdminUserSummary } from "../lib/api-types";
import { postToApi } from "../lib/client-api";
import { getHouseholdRoleLabel } from "../lib/role-labels";

type AdminHouseholdManagementPanelProps = {
  households: AdminHouseholdSummary[];
  users: AdminUserSummary[];
};

type HouseholdSelectFieldProps = {
  households: AdminHouseholdSummary[];
  label: string;
  name: string;
  value: string;
  onChange: (nextValue: string) => void;
};

function HouseholdSelectField({
  households,
  label,
  name,
  value,
  onChange,
}: HouseholdSelectFieldProps) {
  return (
    <label className="field compact household-selector-field">
      <span>{label}</span>
      <select
        name={name}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={households.length === 0}
      >
        <option value="">Select a household</option>
        {households.map((household) => (
          <option key={household.external_id} value={household.external_id}>
            {household.name}
          </option>
        ))}
      </select>
    </label>
  );
}

function countHouseholdAdmins(household: AdminHouseholdSummary | null) {
  return (
    household?.memberships.filter((membership) => membership.role === "household_admin").length ?? 0
  );
}

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
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleteSuccess, setDeleteSuccess] = useState<string | null>(null);
  const [deletePending, setDeletePending] = useState(false);
  const [deleteConfirmation, setDeleteConfirmation] = useState("");
  const [acknowledgeLastHousehold, setAcknowledgeLastHousehold] = useState(false);
  const [selectedHousehold, setSelectedHousehold] = useState(households[0]?.external_id ?? "");
  const [selectedUser, setSelectedUser] = useState(users[0]?.external_id ?? "");
  const [selectedRole, setSelectedRole] = useState("household_admin");

  const selectedHouseholdSummary = useMemo(
    () => households.find((household) => household.external_id === selectedHousehold) ?? null,
    [households, selectedHousehold],
  );
  const isLastHousehold = households.length === 1;
  const adminCount = countHouseholdAdmins(selectedHouseholdSummary);
  const availableUsers = useMemo(() => {
    const assignedUserIds = new Set(selectedHouseholdSummary?.memberships.map((membership) => membership.user_external_id) ?? []);
    return users.filter((user) => !assignedUserIds.has(user.external_id));
  }, [selectedHouseholdSummary, users]);
  const resolvedSelectedUser = availableUsers.some((user) => user.external_id === selectedUser)
    ? selectedUser
    : (availableUsers[0]?.external_id ?? "");

  function handleHouseholdSelection(nextValue: string) {
    setSelectedHousehold(nextValue);
    setDeleteConfirmation("");
    setAcknowledgeLastHousehold(false);
    setSelectedUser("");
    setMembershipError(null);
    setMembershipSuccess(null);
    setDeleteError(null);
    setDeleteSuccess(null);
  }

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
      setSelectedHousehold(created.external_id);
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
    const userExternalId = String(formData.get("user_external_id") ?? "");
    const role = String(formData.get("role") ?? "");

    if (!selectedHouseholdSummary) {
      setMembershipError("Select a household first.");
      setMembershipPending(false);
      return;
    }

    try {
      const created = await postToApi<{ email: string; role: string }>(
        `/api/platform-admin/households/${selectedHouseholdSummary.external_id}/memberships`,
        {
          user_external_id: userExternalId,
          role,
        },
      );
      setMembershipSuccess(`Assigned ${created.email} as ${getHouseholdRoleLabel(created.role)}.`);
      setSelectedUser("");
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

    setMembershipError(null);
    setMembershipSuccess(null);
    setMembershipPending(true);
    try {
      const response = await postToApi<{ message: string }>(
        `/api/platform-admin/households/${selectedHouseholdSummary.external_id}/memberships/${membershipExternalId}/remove`,
        {},
      );
      setMembershipSuccess(response.message);
      router.refresh();
    } catch (requestError) {
      setMembershipError(
        requestError instanceof Error ? requestError.message : "Membership removal failed.",
      );
    } finally {
      setMembershipPending(false);
    }
  }

  async function handleDeleteHousehold(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedHouseholdSummary) {
      return;
    }

    setDeleteError(null);
    setDeleteSuccess(null);
    setDeletePending(true);
    try {
      const response = await postToApi<{ message: string }>(
        `/api/platform-admin/households/${selectedHouseholdSummary.external_id}/delete`,
        {
          confirm_household_name: deleteConfirmation,
          acknowledge_last_household_deletion: acknowledgeLastHousehold,
        },
      );
      setDeleteSuccess(response.message);
      setDeleteConfirmation("");
      setAcknowledgeLastHousehold(false);
      router.refresh();
    } catch (requestError) {
      setDeleteError(
        requestError instanceof Error ? requestError.message : "Household deletion failed.",
      );
    } finally {
      setDeletePending(false);
    }
  }

  return (
    <div className="stack">
      <section className="household-admin-console">
        <form
          className="panel household-create-panel"
          onSubmit={handleCreateHousehold}
          data-testid="admin-create-household-form"
        >
          <p className="eyebrow">Households</p>
          <h2>Create household</h2>
          <p className="section-copy">
            Add a household, then manage members from the shared workspace beside it.
          </p>
          <div className="household-create-form">
            <label className="field">
              <span>Household name</span>
              <input name="name" placeholder="Brown family" required />
            </label>
            <button type="submit" className="primary-button" disabled={householdPending}>
              {householdPending ? "Creating..." : "Create household"}
            </button>
          </div>
          <div className="tag-row">
            <span className="pill">{households.length} total households</span>
          </div>
          {householdError ? <p className="error-text">{householdError}</p> : null}
          {householdSuccess ? <p className="status-note">{householdSuccess}</p> : null}
        </form>

        <article className="panel household-membership-panel">
          <div className="setup-card-toolbar household-management-toolbar">
            <div className="stack compact-stack">
              <p className="eyebrow">Memberships</p>
              <h2>Manage memberships</h2>
              <p className="section-copy">
                Choose a household to review members and add new assignments without leaving the
                page.
              </p>
            </div>
            <HouseholdSelectField
              households={households}
              label="Household"
              name="membership_household_external_id"
              value={selectedHousehold}
              onChange={handleHouseholdSelection}
            />
          </div>

          {households.length === 0 ? (
            <p className="section-copy">Create a household before managing memberships.</p>
          ) : selectedHouseholdSummary ? (
            <div className="stack">
              <div className="household-summary-grid">
                <div className="household-summary-card">
                  <span className="eyebrow">External ID</span>
                  <code>{selectedHouseholdSummary.external_id}</code>
                </div>
                <div className="household-summary-card">
                  <span className="eyebrow">Members</span>
                  <strong>{selectedHouseholdSummary.memberships.length}</strong>
                </div>
                <div className="household-summary-card">
                  <span className="eyebrow">Admins</span>
                  <strong>{adminCount}</strong>
                </div>
                <div className="household-summary-card household-summary-action">
                  <Link
                    href={`/app/households/${selectedHouseholdSummary.external_id}`}
                    className="secondary-link"
                  >
                    Open pantry
                  </Link>
                </div>
              </div>

              <div className="household-management-grid">
                <div className="panel embedded-panel household-members-list-panel">
                  <div className="stack compact-stack">
                    <h3>Current members</h3>
                    <p className="section-copy">
                      Review everyone in {selectedHouseholdSummary.name} and remove access when
                      needed.
                    </p>
                  </div>

                  {selectedHouseholdSummary.memberships.length === 0 ? (
                    <p className="section-copy">No members are assigned yet.</p>
                  ) : (
                    <div className="household-members-list">
                      {selectedHouseholdSummary.memberships.map((membership) => (
                        <div
                          key={membership.membership_external_id}
                          className="household-member-row"
                        >
                          <div className="household-member-details">
                            <strong>{membership.display_name ?? membership.email}</strong>
                            <div className="helper-text">{membership.email}</div>
                          </div>
                          <div className="household-member-controls">
                            <span className="pill">
                              {getHouseholdRoleLabel(membership.role, { detailed: true })}
                            </span>
                            <button
                              type="button"
                              className="ghost-button"
                              onClick={() =>
                                void handleRemoveMembership(
                                  membership.membership_external_id,
                                  membership.display_name ?? membership.email,
                                )
                              }
                              disabled={membershipPending}
                            >
                              Remove
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <form
                  className="panel embedded-panel household-membership-form-panel"
                  onSubmit={handleAssignMembership}
                  data-testid="admin-manage-memberships-form"
                >
                  <div className="stack compact-stack">
                    <h3>Add someone</h3>
                    <p className="section-copy">
                      Assign access to this household and choose the role they should start with.
                    </p>
                  </div>

                  {users.length === 0 ? (
                    <p className="section-copy">
                      Create at least one user first. Membership assignment stays disabled until a
                      user exists.
                    </p>
                  ) : availableUsers.length === 0 ? (
                    <p className="section-copy">
                      Every current user is already assigned to this household.
                    </p>
                  ) : (
                    <div className="stack">
                      <label className="field">
                        <span>User</span>
                        <select
                          name="user_external_id"
                          value={resolvedSelectedUser}
                          onChange={(event) => setSelectedUser(event.target.value)}
                          required
                        >
                          <option value="">Select a user</option>
                          {availableUsers.map((user) => (
                            <option key={user.external_id} value={user.external_id}>
                              {user.display_name ?? user.email} ({user.email})
                            </option>
                          ))}
                        </select>
                      </label>
                      <label className="field">
                        <span>Role</span>
                        <select
                          name="role"
                          value={selectedRole}
                          onChange={(event) => setSelectedRole(event.target.value)}
                          required
                        >
                          <option value="household_admin">
                            {getHouseholdRoleLabel("household_admin")}
                          </option>
                          <option value="household_user">
                            {getHouseholdRoleLabel("household_user")}
                          </option>
                        </select>
                      </label>
                      <button
                        type="submit"
                        className="primary-button"
                        disabled={membershipPending || availableUsers.length === 0}
                      >
                        {membershipPending ? "Saving..." : "Add membership"}
                      </button>
                    </div>
                  )}

                  <p className="helper-text">
                    Need to remove access? Use the member list so routine assignment stays in one
                    place.
                  </p>
                </form>
              </div>
            </div>
          ) : (
            <p className="section-copy">Select a household to manage memberships.</p>
          )}

          {membershipError ? <p className="error-text">{membershipError}</p> : null}
          {membershipSuccess ? <p className="status-note">{membershipSuccess}</p> : null}
        </article>
      </section>

      <form
        className="panel household-delete-panel"
        onSubmit={handleDeleteHousehold}
        data-testid="admin-household-delete-form"
      >
        <div className="setup-card-toolbar household-management-toolbar">
          <div className="stack compact-stack">
            <p className="eyebrow">Destructive Action</p>
            <h2>Delete household</h2>
            <p className="section-copy">
              Keep deletion separate from day-to-day membership work. This action removes the
              selected household and all of its related records.
            </p>
          </div>
          <HouseholdSelectField
            households={households}
            label="Household"
            name="delete_household_external_id"
            value={selectedHousehold}
            onChange={handleHouseholdSelection}
          />
        </div>

        {households.length === 0 ? (
          <p className="section-copy">Create a household before using deletion controls.</p>
        ) : selectedHouseholdSummary ? (
          <div className="household-delete-grid">
            <div className="warning-callout">
              <strong>Before you continue</strong>
              <p>
                Deleting {selectedHouseholdSummary.name} removes pantry, recipe, import,
                membership, AI, and audit records for that household.
              </p>
            </div>

            <div className="stack">
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
              <button
                type="submit"
                className="primary-button"
                disabled={
                  deletePending ||
                  deleteConfirmation !== selectedHouseholdSummary.name ||
                  (isLastHousehold && !acknowledgeLastHousehold)
                }
              >
                {deletePending ? "Working..." : "Delete household"}
              </button>
            </div>
          </div>
        ) : null}

        {deleteError ? <p className="error-text">{deleteError}</p> : null}
        {deleteSuccess ? <p className="status-note">{deleteSuccess}</p> : null}
      </form>
    </div>
  );
}

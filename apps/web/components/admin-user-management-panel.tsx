"use client";

import { FormEvent, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import type { AdminHouseholdSummary, AdminUserSummary } from "../lib/api-types";
import { patchToApi, postToApi } from "../lib/client-api";
import { getPlatformRoleLabel } from "../lib/role-labels";
import { ModalShell } from "./modal-shell";

type AdminUserManagementPanelProps = {
  users: AdminUserSummary[];
  households: AdminHouseholdSummary[];
  passwordResetEnabled: boolean;
};

type MembershipDraft = {
  household_external_id: string;
  role: "" | "household_admin" | "household_user";
};

export function AdminUserManagementPanel({
  users,
  households,
  passwordResetEnabled,
}: AdminUserManagementPanelProps) {
  const router = useRouter();
  const [editingUser, setEditingUser] = useState<AdminUserSummary | null>(null);
  const [pendingResetUserId, setPendingResetUserId] = useState<string | null>(null);
  const [pageError, setPageError] = useState<string | null>(null);
  const [pageStatus, setPageStatus] = useState<string | null>(null);

  async function sendPasswordReset(user: AdminUserSummary) {
    setPendingResetUserId(user.external_id);
    setPageError(null);
    setPageStatus(null);
    try {
      const response = await postToApi<{ message: string }>(
        `/api/platform-admin/users/${user.external_id}/send-password-reset`,
        {},
      );
      setPageStatus(response.message);
    } catch (requestError) {
      setPageError(
        requestError instanceof Error ? requestError.message : "Could not send a password reset email.",
      );
    } finally {
      setPendingResetUserId(null);
    }
  }

  return (
    <>
      <section className="panel stack">
        <div className="inventory-header">
          <div className="stack compact-stack">
            <p className="eyebrow">Users</p>
            <h2>Manage users</h2>
            <p className="section-copy">
              Edit account details, platform access, and household memberships in one place.
            </p>
          </div>
          {passwordResetEnabled ? <span className="pill is-success">Reset email enabled</span> : null}
        </div>
        {pageError ? <p className="error-text">{pageError}</p> : null}
        {pageStatus ? <p className="status-note">{pageStatus}</p> : null}
        <div className="table-wrap">
          <table className="data-table admin-users-table">
            <thead>
              <tr>
                <th>Sign-in ID</th>
                <th>Display name</th>
                <th>Access</th>
                <th>Households</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.external_id}>
                  <td>{user.email}</td>
                  <td>{user.display_name ?? "Unspecified"}</td>
                  <td>{getPlatformRoleLabel(user.platform_role, { detailed: true })}</td>
                  <td>
                    {user.memberships.length > 0
                      ? user.memberships
                          .map((membership) => `${membership.household_name} (${membership.role.replace("household_", "")})`)
                          .join(", ")
                      : "No household memberships"}
                  </td>
                  <td>
                    <div className="page-actions">
                      <button
                        type="button"
                        className="ghost-button compact-button"
                        onClick={() => setEditingUser(user)}
                      >
                        Edit
                      </button>
                      {passwordResetEnabled ? (
                        <button
                          type="button"
                          className="ghost-button compact-button"
                          disabled={pendingResetUserId === user.external_id}
                          onClick={() => void sendPasswordReset(user)}
                        >
                          {pendingResetUserId === user.external_id ? "Sending..." : "Send reset"}
                        </button>
                      ) : null}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {editingUser ? (
        <AdminUserEditDialog
          households={households}
          user={editingUser}
          passwordResetEnabled={passwordResetEnabled}
          onClose={() => setEditingUser(null)}
          onSaved={() => {
            setEditingUser(null);
            router.refresh();
          }}
          onResetSent={(message) => {
            setPageStatus(message);
            setEditingUser(null);
            router.refresh();
          }}
        />
      ) : null}
    </>
  );
}

type AdminUserEditDialogProps = {
  user: AdminUserSummary;
  households: AdminHouseholdSummary[];
  passwordResetEnabled: boolean;
  onClose: () => void;
  onSaved: () => void;
  onResetSent: (message: string) => void;
};

function AdminUserEditDialog({
  user,
  households,
  passwordResetEnabled,
  onClose,
  onSaved,
  onResetSent,
}: AdminUserEditDialogProps) {
  const [email, setEmail] = useState(user.email);
  const [displayName, setDisplayName] = useState(user.display_name ?? "");
  const [platformRole, setPlatformRole] = useState(user.platform_role ?? "");
  const [memberships, setMemberships] = useState<MembershipDraft[]>(
    households.map((household) => {
      const membership = user.memberships.find(
        (candidate) => candidate.household_external_id === household.external_id,
      );
      return {
        household_external_id: household.external_id,
        role: (membership?.role as MembershipDraft["role"]) ?? "",
      };
    }),
  );
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const activeMembershipCount = useMemo(
    () => memberships.filter((membership) => membership.role).length,
    [memberships],
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError(null);
    setStatusMessage(null);

    try {
      await patchToApi<AdminUserSummary>(`/api/platform-admin/users/${user.external_id}`, {
        email,
        display_name: displayName.trim() || null,
        platform_role: platformRole || null,
        memberships: memberships
          .filter((membership) => membership.role)
          .map((membership) => ({
            household_external_id: membership.household_external_id,
            role: membership.role,
          })),
      });
      onSaved();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not update this user.");
    } finally {
      setPending(false);
    }
  }

  async function sendResetFromDialog() {
    setPending(true);
    setError(null);
    setStatusMessage(null);
    try {
      const response = await postToApi<{ message: string }>(
        `/api/platform-admin/users/${user.external_id}/send-password-reset`,
        {},
      );
      setStatusMessage(response.message);
      onResetSent(response.message);
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : "Could not send a password reset email.",
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <ModalShell
      title={`Edit ${user.display_name ?? user.email}`}
      description="Update account details, platform access, and household memberships."
      onClose={onClose}
      panelClassName="modal-panel modal-panel-wide"
    >
      <form className="stack" onSubmit={handleSubmit}>
        <div className="content-grid">
          <label className="field">
            <span>Username or email</span>
            <input
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoCapitalize="none"
              autoCorrect="off"
              spellCheck={false}
              required
            />
          </label>
          <label className="field">
            <span>Display name</span>
            <input
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              placeholder="Alex"
            />
          </label>
          <label className="field">
            <span>Platform role</span>
            <select value={platformRole} onChange={(event) => setPlatformRole(event.target.value)}>
              <option value="">Standard user</option>
              <option value="platform_admin">Platform admin</option>
            </select>
          </label>
          <article className="inline-status-card">
            <strong>Household memberships</strong>
            <p className="helper-text">
              {activeMembershipCount > 0
                ? `${activeMembershipCount} household membership${activeMembershipCount === 1 ? "" : "s"} assigned.`
                : "This user is not assigned to any household yet."}
            </p>
          </article>
        </div>

        <div className="admin-user-membership-grid">
          {households.map((household, index) => (
            <label key={household.external_id} className="field compact">
              <span>{household.name}</span>
              <select
                value={memberships[index]?.role ?? ""}
                onChange={(event) =>
                  setMemberships((current) =>
                    current.map((membership, membershipIndex) =>
                      membershipIndex === index
                        ? {
                            ...membership,
                            role: event.target.value as MembershipDraft["role"],
                          }
                        : membership,
                    ),
                  )
                }
              >
                <option value="">No membership</option>
                <option value="household_user">Household user</option>
                <option value="household_admin">Household admin</option>
              </select>
            </label>
          ))}
        </div>

        {error ? <p className="error-text">{error}</p> : null}
        {statusMessage ? <p className="status-note">{statusMessage}</p> : null}
        <div className="page-actions">
          <button type="submit" className="primary-button" disabled={pending}>
            {pending ? "Saving..." : "Save user"}
          </button>
          {passwordResetEnabled ? (
            <button
              type="button"
              className="ghost-button"
              disabled={pending}
              onClick={() => void sendResetFromDialog()}
            >
              Send reset email
            </button>
          ) : null}
        </div>
      </form>
    </ModalShell>
  );
}

"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import type {
  SetupStatusResponse,
  SetupWizardAssignmentSummary,
  SetupWizardDietaryUserSummary,
  SetupWizardStateResponse,
  SetupWizardUserSummary,
  SessionResponse
} from "../lib/api-types";
import { postToApi, putToApi } from "../lib/client-api";
import { SetupProgress } from "./setup-progress";

type SetupStepKey = SetupStatusResponse["steps"][number]["key"];

type SetupWizardProps = {
  initialState: SetupWizardStateResponse;
  initialStep: SetupStepKey;
};

type PasswordDraft = {
  password: string;
  confirm: string;
};

const STEP_ORDER: SetupStepKey[] = [
  "welcome",
  "users",
  "household",
  "public_url",
  "dietary",
  "ai",
  "smtp",
  "review"
];

const LOCATION_SUGGESTIONS = ["Fridge", "Freezer", "Cupboard", "Pantry shelf"];
const DIETARY_SUGGESTIONS = [
  "Vegan",
  "Vegetarian",
  "Pescatarian",
  "Dairy-free",
  "Gluten-free",
  "Nut allergy",
  "Egg-free"
];

function nextStep(currentStep: SetupStepKey): SetupStepKey {
  const currentIndex = STEP_ORDER.indexOf(currentStep);
  return STEP_ORDER[Math.min(currentIndex + 1, STEP_ORDER.length - 1)];
}

function previousStep(currentStep: SetupStepKey): SetupStepKey {
  const currentIndex = STEP_ORDER.indexOf(currentStep);
  return STEP_ORDER[Math.max(currentIndex - 1, 0)];
}

function createStageId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `stage-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function findAssignment(
  assignments: SetupWizardAssignmentSummary[],
  stageUserId: string
): SetupWizardAssignmentSummary | undefined {
  return assignments.find((assignment) => assignment.stage_user_id === stageUserId);
}

function findUserPreferences(
  preferences: SetupWizardDietaryUserSummary[],
  stageUserId: string
) {
  return preferences.find((item) => item.stage_user_id === stageUserId)?.preferences ?? [];
}

function summarizeUser(user: SetupWizardUserSummary) {
  return user.display_name ? `${user.display_name} (${user.login})` : user.login;
}

function renderSavedPasswordHint(user: SetupWizardUserSummary) {
  return user.password_saved ? "Password saved" : "Password not saved yet";
}

function PasswordFields({
  label,
  draft,
  onChange,
  onBlur
}: {
  label: string;
  draft: PasswordDraft;
  onChange: (nextDraft: PasswordDraft) => void;
  onBlur?: () => void;
}) {
  return (
    <div className="content-grid">
      <label className="field">
        <span>{label}</span>
        <input
          type="password"
          value={draft.password}
          minLength={8}
          onChange={(event) => onChange({ ...draft, password: event.target.value })}
          onBlur={onBlur}
          placeholder="At least 8 characters"
        />
      </label>
      <label className="field">
        <span>Confirm password</span>
        <input
          type="password"
          value={draft.confirm}
          minLength={8}
          onChange={(event) => onChange({ ...draft, confirm: event.target.value })}
          onBlur={onBlur}
          placeholder="Repeat the password"
        />
      </label>
    </div>
  );
}

function TokenEditor({
  tokens,
  suggestions,
  newValue,
  onNewValueChange,
  onAddToken,
  onRemoveToken,
  label,
  placeholder
}: {
  tokens: string[];
  suggestions: string[];
  newValue: string;
  onNewValueChange: (value: string) => void;
  onAddToken: (value: string) => void;
  onRemoveToken: (value: string) => void;
  label: string;
  placeholder: string;
}) {
  return (
    <div className="stack">
      <label className="field">
        <span>{label}</span>
        <div className="token-input-row">
          <input
            value={newValue}
            onChange={(event) => onNewValueChange(event.target.value)}
            placeholder={placeholder}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                onAddToken(newValue);
              }
            }}
          />
          <button type="button" className="ghost-button" onClick={() => onAddToken(newValue)}>
            Add
          </button>
        </div>
      </label>
      <div className="tag-row">
        {tokens.map((token) => (
          <button
            key={token}
            type="button"
            className="tag is-removable"
            onClick={() => onRemoveToken(token)}
          >
            {token}
            <span>Remove</span>
          </button>
        ))}
      </div>
      <div className="tag-row">
        {suggestions.map((suggestion) => (
          <button
            key={suggestion}
            type="button"
            className="tag is-suggestion"
            onClick={() => onAddToken(suggestion)}
          >
            {suggestion}
          </button>
        ))}
      </div>
    </div>
  );
}

export function SetupWizard({ initialState, initialStep }: SetupWizardProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [wizard, setWizard] = useState(initialState);
  const [currentStep, setCurrentStep] = useState<SetupStepKey>(initialStep);
  const [adminPasswordDraft, setAdminPasswordDraft] = useState<PasswordDraft>({
    password: "",
    confirm: ""
  });
  const [userPasswordDrafts, setUserPasswordDrafts] = useState<Record<string, PasswordDraft>>({});
  const [newLocation, setNewLocation] = useState("");
  const [newHouseholdDietaryPreference, setNewHouseholdDietaryPreference] = useState("");
  const [newUserDietaryPreference, setNewUserDietaryPreference] = useState<Record<string, string>>({});
  const [aiApiKey, setAiApiKey] = useState("");
  const [smtpPassword, setSmtpPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  const allUsers = [wizard.admin_user, ...wizard.initial_users];

  function moveToStep(step: SetupStepKey) {
    setCurrentStep(step);
    const params = new URLSearchParams(searchParams.toString());
    params.set("step", step);
    router.replace(`/setup?${params.toString()}`, { scroll: false });
  }

  function updateWizard(nextState: SetupWizardStateResponse, savedMessage?: string) {
    setWizard(nextState);
    setError(null);
    setStatusMessage(savedMessage ?? "Progress saved.");
  }

  function scheduleStepSave(step: SetupStepKey) {
    window.setTimeout(() => {
      void persistStep(step, { suppressErrors: true });
    }, 0);
  }

  async function persistHouseholdSnapshot(snapshot: SetupWizardStateResponse) {
    try {
      updateWizard(
        await putToApi<SetupWizardStateResponse>("/api/setup/wizard/household", {
          household_name: snapshot.household_name ?? "",
          location_group_name: snapshot.location_group_name ?? "",
          storage_locations: snapshot.storage_locations,
          household_assignments: snapshot.household_assignments
        }),
        "Household details saved."
      );
    } catch {
      // Keep inline interaction resilient; the explicit Next save still surfaces errors.
    }
  }

  async function persistDietarySnapshot(snapshot: SetupWizardStateResponse) {
    try {
      updateWizard(
        await putToApi<SetupWizardStateResponse>("/api/setup/wizard/dietary", {
          household_preferences: snapshot.household_dietary_preferences,
          user_preferences: snapshot.user_dietary_preferences
        }),
        "Dietary preferences saved."
      );
    } catch {
      // Keep inline interaction resilient; the explicit Next save still surfaces errors.
    }
  }

  async function persistStep(
    step: SetupStepKey,
    options?: { suppressErrors?: boolean }
  ): Promise<boolean> {
    const suppressErrors = Boolean(options?.suppressErrors);

    if (step === "users") {
      if (
        adminPasswordDraft.password &&
        adminPasswordDraft.password !== adminPasswordDraft.confirm
      ) {
        if (!suppressErrors) {
          setError("The platform admin password confirmation does not match.");
        }
        return false;
      }
      if (adminPasswordDraft.password && adminPasswordDraft.password.length < 8) {
        if (!suppressErrors) {
          setError("Passwords must be at least 8 characters.");
        }
        return false;
      }

      for (const draft of Object.values(userPasswordDrafts)) {
        if (draft.password && draft.password !== draft.confirm) {
          if (!suppressErrors) {
            setError("Each staged user password must match its confirmation.");
          }
          return false;
        }
        if (draft.password && draft.password.length < 8) {
          if (!suppressErrors) {
            setError("Passwords must be at least 8 characters.");
          }
          return false;
        }
      }
    }

    setIsSaving(true);
    if (!suppressErrors) {
      setError(null);
      setStatusMessage(null);
    }

    try {
      if (step === "welcome") {
        updateWizard(
          await putToApi<SetupWizardStateResponse>("/api/setup/wizard/welcome", {
            acknowledged: true
          }),
          "Welcome step saved."
        );
      }

      if (step === "users") {
        const initialUsersPayload = wizard.initial_users.map((user) => ({
          stage_id: user.stage_id,
          login: user.login,
          display_name: user.display_name,
          password: userPasswordDrafts[user.stage_id]?.password || null
        }));
        updateWizard(
          await putToApi<SetupWizardStateResponse>("/api/setup/wizard/users", {
            admin_login: wizard.admin_user.login,
            admin_display_name: wizard.admin_user.display_name,
            admin_password: adminPasswordDraft.password || null,
            initial_users: initialUsersPayload
          }),
          "Users saved."
        );
        setAdminPasswordDraft({ password: "", confirm: "" });
        setUserPasswordDrafts({});
      }

      if (step === "household") {
        updateWizard(
          await putToApi<SetupWizardStateResponse>("/api/setup/wizard/household", {
            household_name: wizard.household_name ?? "",
            location_group_name: wizard.location_group_name ?? "",
            storage_locations: wizard.storage_locations,
            household_assignments: wizard.household_assignments
          }),
          "Household details saved."
        );
      }

      if (step === "public_url") {
        updateWizard(
          await putToApi<SetupWizardStateResponse>("/api/setup/wizard/public-url", {
            public_base_url: wizard.public_base_url
          }),
          "Public browser URL saved."
        );
      }

      if (step === "dietary") {
        updateWizard(
          await putToApi<SetupWizardStateResponse>("/api/setup/wizard/dietary", {
            household_preferences: wizard.household_dietary_preferences,
            user_preferences: wizard.user_dietary_preferences
          }),
          "Dietary preferences saved."
        );
      }

      if (step === "ai") {
        updateWizard(
          await putToApi<SetupWizardStateResponse>("/api/setup/wizard/ai", {
            provider_type: wizard.ai_config.provider_type,
            base_url: wizard.ai_config.base_url,
            default_model: wizard.ai_config.default_model,
            api_key: aiApiKey || null,
            is_enabled: wizard.ai_config.is_enabled
          }),
          "AI settings saved."
        );
        setAiApiKey("");
      }

      if (step === "smtp") {
        updateWizard(
          await putToApi<SetupWizardStateResponse>("/api/setup/wizard/smtp", {
            host: wizard.smtp_config.host,
            port: wizard.smtp_config.port,
            username: wizard.smtp_config.username,
            password: smtpPassword || null,
            from_email: wizard.smtp_config.from_email,
            from_name: wizard.smtp_config.from_name,
            security: wizard.smtp_config.security,
            is_enabled: wizard.smtp_config.is_enabled
          }),
          "SMTP settings saved."
        );
        setSmtpPassword("");
      }
      return true;
    } catch (requestError) {
      if (!suppressErrors) {
        setError(requestError instanceof Error ? requestError.message : "Save failed.");
      }
      return false;
    } finally {
      setIsSaving(false);
    }
  }

  async function handleNext() {
    if (currentStep !== "review") {
      const saved = await persistStep(currentStep);
      if (saved) {
        moveToStep(nextStep(currentStep));
      }
    }
  }

  async function handleCompleteSetup() {
    setIsSaving(true);
    setError(null);
    setStatusMessage(null);
    try {
      const response = await postToApi<SessionResponse>("/api/setup/wizard/finalize", {});
      setStatusMessage(`Setup complete. Signed in as ${response.user.email}.`);
      router.push("/app");
      router.refresh();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Setup completion failed.");
    } finally {
      setIsSaving(false);
    }
  }

  function updateAdmin(fields: Partial<SetupWizardUserSummary>) {
    setWizard((current) => ({
      ...current,
      admin_user: {
        ...current.admin_user,
        ...fields
      }
    }));
  }

  function updateInitialUser(stageId: string, fields: Partial<SetupWizardUserSummary>) {
    setWizard((current) => ({
      ...current,
      initial_users: current.initial_users.map((user) =>
        user.stage_id === stageId
          ? {
              ...user,
              ...fields
            }
          : user
      )
    }));
  }

  function addInitialUser() {
    setWizard((current) => ({
      ...current,
      initial_users: [
        ...current.initial_users,
        {
          stage_id: createStageId(),
          login: "",
          display_name: "",
          password_saved: false,
          is_platform_admin: false
        }
      ]
    }));
    scheduleStepSave("users");
  }

  function removeInitialUser(stageId: string) {
    setWizard((current) => ({
      ...current,
      initial_users: current.initial_users.filter((user) => user.stage_id !== stageId),
      household_assignments: current.household_assignments.filter(
        (assignment) => assignment.stage_user_id !== stageId
      ),
      user_dietary_preferences: current.user_dietary_preferences.filter(
        (preference) => preference.stage_user_id !== stageId
      )
    }));
    setUserPasswordDrafts((current) => {
      const nextDrafts = { ...current };
      delete nextDrafts[stageId];
      return nextDrafts;
    });
    scheduleStepSave("users");
  }

  function toggleHouseholdAssignment(stageUserId: string, selected: boolean) {
    const nextWizard = {
      ...wizard,
      household_assignments: selected
        ? [
            ...wizard.household_assignments.filter(
              (assignment) => assignment.stage_user_id !== stageUserId
            ),
            {
              stage_user_id: stageUserId,
              role: "household_user" as const
            }
          ]
        : wizard.household_assignments.filter((assignment) => assignment.stage_user_id !== stageUserId)
    };
    setWizard(nextWizard);
    void persistHouseholdSnapshot(nextWizard);
  }

  function updateHouseholdAssignmentRole(stageUserId: string, role: "household_admin" | "household_user") {
    const nextWizard = {
      ...wizard,
      household_assignments: wizard.household_assignments.map((assignment) =>
        assignment.stage_user_id === stageUserId
          ? {
              ...assignment,
              role
            }
          : assignment
      )
    };
    setWizard(nextWizard);
    void persistHouseholdSnapshot(nextWizard);
  }

  function addStorageLocation(value: string) {
    const trimmed = value.trim();
    if (!trimmed) {
      return;
    }
    const nextWizard = {
      ...wizard,
      storage_locations: Array.from(new Set([...wizard.storage_locations, trimmed]))
    };
    setWizard(nextWizard);
    setNewLocation("");
    void persistHouseholdSnapshot(nextWizard);
  }

  function removeStorageLocation(location: string) {
    const nextWizard = {
      ...wizard,
      storage_locations: wizard.storage_locations.filter((item) => item !== location)
    };
    setWizard(nextWizard);
    void persistHouseholdSnapshot(nextWizard);
  }

  function addHouseholdDietaryPreference(value: string) {
    const trimmed = value.trim();
    if (!trimmed) {
      return;
    }
    const nextWizard = {
      ...wizard,
      household_dietary_preferences: Array.from(
        new Set([...wizard.household_dietary_preferences, trimmed])
      )
    };
    setWizard(nextWizard);
    setNewHouseholdDietaryPreference("");
    void persistDietarySnapshot(nextWizard);
  }

  function removeHouseholdDietaryPreference(value: string) {
    const nextWizard = {
      ...wizard,
      household_dietary_preferences: wizard.household_dietary_preferences.filter(
        (item) => item !== value
      )
    };
    setWizard(nextWizard);
    void persistDietarySnapshot(nextWizard);
  }

  function addUserDietaryPreference(stageUserId: string, value: string) {
    const trimmed = value.trim();
    if (!trimmed) {
      return;
    }
    const existing = findUserPreferences(wizard.user_dietary_preferences, stageUserId);
    const nextPreferences = Array.from(new Set([...existing, trimmed]));
    const others = wizard.user_dietary_preferences.filter(
      (item) => item.stage_user_id !== stageUserId
    );
    const nextWizard = {
      ...wizard,
      user_dietary_preferences: [
        ...others,
        {
          stage_user_id: stageUserId,
          preferences: nextPreferences
        }
      ]
    };
    setWizard(nextWizard);
    setNewUserDietaryPreference((current) => ({ ...current, [stageUserId]: "" }));
    void persistDietarySnapshot(nextWizard);
  }

  function removeUserDietaryPreference(stageUserId: string, value: string) {
    const nextWizard = {
      ...wizard,
      user_dietary_preferences: wizard.user_dietary_preferences
        .map((item) =>
          item.stage_user_id === stageUserId
            ? {
                ...item,
                preferences: item.preferences.filter((preference) => preference !== value)
              }
            : item
        )
        .filter((item) => item.preferences.length > 0)
    };
    setWizard(nextWizard);
    void persistDietarySnapshot(nextWizard);
  }

  const renderStep = () => {
    if (currentStep === "welcome") {
      return (
        <section className="setup-step-card">
          <p className="eyebrow">First Run</p>
          <h1>Set up Pantry once, then finalize when you’re ready.</h1>
          <p className="lede compact">
            This guided setup stages your admin account, household, storage locations, preferences,
            and optional integrations. Nothing is written into Pantry’s live tables until you click
            <strong> Complete Setup</strong> on the final step.
          </p>
          <div className="setup-highlight-grid">
            <article className="setup-highlight">
              <strong>Professional first run</strong>
              <p>Move through the steps at your own pace with clear progress and review controls.</p>
            </article>
            <article className="setup-highlight">
              <strong>Progress persists</strong>
              <p>Staged details survive refreshes so you can come back without starting over.</p>
            </article>
            <article className="setup-highlight">
              <strong>Safe finalization</strong>
              <p>Pantry only marks setup complete after the final transactional commit succeeds.</p>
            </article>
          </div>
        </section>
      );
    }

    if (currentStep === "users") {
      return (
        <section className="setup-step-card" data-testid="setup-users-step">
          <p className="eyebrow">Step 2</p>
          <h1>Admin account and initial users</h1>
          <p className="step-copy">
            Start with the installation owner, then add any extra people you want ready on day one.
            Passwords are stored securely in staged form until final completion.
          </p>

          <div className="setup-subsection">
            <div className="setup-subsection-heading">
              <h2>Main platform admin</h2>
              <span className="pill is-required">Required</span>
            </div>
            <div className="content-grid">
              <label className="field">
                <span>Username or email</span>
                <input
                  value={wizard.admin_user.login}
                  onChange={(event) => updateAdmin({ login: event.target.value })}
                  placeholder="owner"
                />
              </label>
              <label className="field">
                <span>Display name</span>
                <input
                  value={wizard.admin_user.display_name ?? ""}
                  onChange={(event) => updateAdmin({ display_name: event.target.value })}
                  placeholder="Pantry owner"
                />
              </label>
            </div>
            <PasswordFields
              label={wizard.admin_user.password_saved ? "Replace password" : "Password"}
              draft={adminPasswordDraft}
              onChange={setAdminPasswordDraft}
            />
            <p className="helper-text">{renderSavedPasswordHint(wizard.admin_user)}</p>
          </div>

          <div className="setup-subsection">
            <div className="setup-subsection-heading">
              <h2>Additional users</h2>
              <button type="button" className="ghost-button" onClick={addInitialUser}>
                Add user
              </button>
            </div>
            <div className="stack">
              {wizard.initial_users.length === 0 ? (
                <div className="empty-state">
                  <p>No extra users staged yet. You can skip this for now and add people later.</p>
                </div>
              ) : null}
              {wizard.initial_users.map((user, index) => (
                <article key={user.stage_id} className="setup-user-card">
                  <div className="setup-card-toolbar">
                    <strong>Initial user {index + 1}</strong>
                    <button
                      type="button"
                      className="inline-danger"
                      onClick={() => removeInitialUser(user.stage_id)}
                    >
                      Remove
                    </button>
                  </div>
                  <div className="content-grid">
                    <label className="field">
                      <span>Username or email</span>
                      <input
                        value={user.login}
                        onChange={(event) =>
                          updateInitialUser(user.stage_id, { login: event.target.value })
                        }
                      />
                    </label>
                    <label className="field">
                      <span>Display name</span>
                      <input
                        value={user.display_name ?? ""}
                        onChange={(event) =>
                          updateInitialUser(user.stage_id, { display_name: event.target.value })
                        }
                      />
                    </label>
                  </div>
                  <PasswordFields
                    label={user.password_saved ? "Replace password" : "Password"}
                    draft={userPasswordDrafts[user.stage_id] ?? { password: "", confirm: "" }}
                    onChange={(draft) =>
                      setUserPasswordDrafts((current) => ({ ...current, [user.stage_id]: draft }))
                    }
                  />
                  <p className="helper-text">{renderSavedPasswordHint(user)}</p>
                </article>
              ))}
            </div>
          </div>
        </section>
      );
    }

    if (currentStep === "household") {
      return (
        <section className="setup-step-card">
          <p className="eyebrow">Step 3</p>
          <h1>First household and storage locations</h1>
          <p className="step-copy">
            Create the first household, name the primary storage area, and stage the places people
            will browse most often.
          </p>

          <div className="content-grid">
            <label className="field">
              <span>Household name</span>
              <input
                value={wizard.household_name ?? ""}
                onChange={(event) =>
                  setWizard((current) => ({ ...current, household_name: event.target.value }))
                }
                onBlur={() => void persistStep("household", { suppressErrors: true })}
                placeholder="Brown household"
              />
            </label>
            <label className="field">
              <span>Storage area label</span>
              <input
                value={wizard.location_group_name ?? ""}
                onChange={(event) =>
                  setWizard((current) => ({ ...current, location_group_name: event.target.value }))
                }
                onBlur={() => void persistStep("household", { suppressErrors: true })}
                placeholder="Kitchen"
              />
            </label>
          </div>

          <TokenEditor
            tokens={wizard.storage_locations}
            suggestions={LOCATION_SUGGESTIONS}
            newValue={newLocation}
            onNewValueChange={setNewLocation}
            onAddToken={(value) => addStorageLocation(value)}
            onRemoveToken={removeStorageLocation}
            label="Initial storage locations"
            placeholder="Add a storage location"
          />

          <div className="setup-subsection">
            <div className="setup-subsection-heading">
              <h2>Who should belong to this household?</h2>
            </div>
            <div className="stack">
              {allUsers.map((user) => {
                const assignment = findAssignment(wizard.household_assignments, user.stage_id);
                const isAdmin = user.is_platform_admin;
                return (
                  <article key={user.stage_id} className="setup-assignment-card">
                    <label className="checkbox-row">
                      <input
                        type="checkbox"
                        checked={isAdmin || Boolean(assignment)}
                        disabled={isAdmin}
                        onChange={(event) =>
                          toggleHouseholdAssignment(user.stage_id, event.target.checked)
                        }
                      />
                      <span>{summarizeUser(user)}</span>
                    </label>
                    <label className="field compact">
                      <span>Household role</span>
                      <select
                        disabled={isAdmin || !assignment}
                        value={isAdmin ? "household_admin" : assignment?.role ?? "household_user"}
                        onChange={(event) =>
                          updateHouseholdAssignmentRole(
                            user.stage_id,
                            event.target.value as "household_admin" | "household_user"
                          )
                        }
                      >
                        <option value="household_admin">Household admin</option>
                        <option value="household_user">Household user</option>
                      </select>
                    </label>
                  </article>
                );
              })}
            </div>
          </div>
        </section>
      );
    }

    if (currentStep === "public_url") {
      return (
        <section className="setup-step-card">
          <p className="eyebrow">Step 4</p>
          <h1>Public browser URL</h1>
          <p className="step-copy">
            Pantry uses this for QR codes and browser links, so it should match the address people
            will actually open on phones and laptops.
          </p>
          <label className="field">
            <span>Public Pantry URL</span>
            <input
              value={wizard.public_base_url ?? ""}
              onChange={(event) =>
                setWizard((current) => ({ ...current, public_base_url: event.target.value }))
              }
              onBlur={() => void persistStep("public_url", { suppressErrors: true })}
              placeholder="https://pantry.example.com"
            />
          </label>
          <div className="setup-example-list">
            <span>Examples</span>
            <code>http://192.168.1.10:3000</code>
            <code>https://pantry.example.com</code>
          </div>
        </section>
      );
    }

    if (currentStep === "dietary") {
      return (
        <section className="setup-step-card">
          <p className="eyebrow">Step 5</p>
          <h1>Dietary preferences</h1>
          <p className="step-copy">
            Capture household defaults now so recipe suggestions and meal planning can grow into the
            right constraints later.
          </p>

          <TokenEditor
            tokens={wizard.household_dietary_preferences}
            suggestions={DIETARY_SUGGESTIONS}
            newValue={newHouseholdDietaryPreference}
            onNewValueChange={setNewHouseholdDietaryPreference}
            onAddToken={addHouseholdDietaryPreference}
            onRemoveToken={removeHouseholdDietaryPreference}
            label="Household-wide preferences"
            placeholder="Add a preference"
          />

          <div className="setup-subsection">
            <div className="setup-subsection-heading">
              <h2>Optional individual preferences</h2>
            </div>
            <div className="stack">
              {allUsers.map((user) => (
                <article key={user.stage_id} className="setup-user-card">
                  <div className="setup-card-toolbar">
                    <strong>{summarizeUser(user)}</strong>
                  </div>
                  <TokenEditor
                    tokens={findUserPreferences(wizard.user_dietary_preferences, user.stage_id)}
                    suggestions={DIETARY_SUGGESTIONS}
                    newValue={newUserDietaryPreference[user.stage_id] ?? ""}
                    onNewValueChange={(value) =>
                      setNewUserDietaryPreference((current) => ({
                        ...current,
                        [user.stage_id]: value
                      }))
                    }
                    onAddToken={(value) => addUserDietaryPreference(user.stage_id, value)}
                    onRemoveToken={(value) => removeUserDietaryPreference(user.stage_id, value)}
                    label="Personal preferences"
                    placeholder="Add a preference"
                  />
                </article>
              ))}
            </div>
          </div>
        </section>
      );
    }

    if (currentStep === "ai") {
      return (
        <section className="setup-step-card">
          <p className="eyebrow">Step 6</p>
          <h1>AI configuration</h1>
          <p className="step-copy">
            Optional. Configure Pantry’s instance-level AI provider now if you want meal and pantry
            suggestions ready after setup.
          </p>
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={wizard.ai_config.is_enabled}
              onChange={(event) =>
                setWizard((current) => ({
                  ...current,
                  ai_config: { ...current.ai_config, is_enabled: event.target.checked }
                }))
              }
            />
            <span>Enable AI suggestions for this Pantry instance.</span>
          </label>
          <div className="content-grid">
            <label className="field">
              <span>Provider type</span>
              <select
                value={wizard.ai_config.provider_type ?? "ollama"}
                onChange={(event) =>
                  setWizard((current) => ({
                    ...current,
                    ai_config: {
                      ...current.ai_config,
                      provider_type: event.target.value as "ollama" | "openai_compatible"
                    }
                  }))
                }
              >
                <option value="ollama">Ollama</option>
                <option value="openai_compatible">OpenAI-compatible</option>
              </select>
            </label>
            <label className="field">
              <span>Base URL</span>
              <input
                value={wizard.ai_config.base_url ?? ""}
                onChange={(event) =>
                  setWizard((current) => ({
                    ...current,
                    ai_config: { ...current.ai_config, base_url: event.target.value }
                  }))
                }
                placeholder="http://host.docker.internal:11434"
              />
            </label>
            <label className="field">
              <span>Default model</span>
              <input
                value={wizard.ai_config.default_model ?? ""}
                onChange={(event) =>
                  setWizard((current) => ({
                    ...current,
                    ai_config: { ...current.ai_config, default_model: event.target.value }
                  }))
                }
                placeholder="llama3.2"
              />
            </label>
            <label className="field">
              <span>API key</span>
              <input
                type="password"
                value={aiApiKey}
                onChange={(event) => setAiApiKey(event.target.value)}
                placeholder={
                  wizard.ai_config.has_api_key
                    ? "Saved. Enter a new key to replace it."
                    : "Optional for Ollama"
                }
              />
            </label>
          </div>
        </section>
      );
    }

    if (currentStep === "smtp") {
      return (
        <section className="setup-step-card">
          <p className="eyebrow">Step 7</p>
          <h1>SMTP configuration</h1>
          <p className="step-copy">
            Optional. Save email delivery settings now for notifications and other outbound mail
            features later.
          </p>
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={wizard.smtp_config.is_enabled}
              onChange={(event) =>
                setWizard((current) => ({
                  ...current,
                  smtp_config: { ...current.smtp_config, is_enabled: event.target.checked }
                }))
              }
            />
            <span>Enable SMTP for this installation.</span>
          </label>
          <div className="content-grid">
            <label className="field">
              <span>SMTP host</span>
              <input
                value={wizard.smtp_config.host ?? ""}
                onChange={(event) =>
                  setWizard((current) => ({
                    ...current,
                    smtp_config: { ...current.smtp_config, host: event.target.value }
                  }))
                }
                placeholder="smtp.example.com"
              />
            </label>
            <label className="field">
              <span>Port</span>
              <input
                type="number"
                value={wizard.smtp_config.port ?? ""}
                onChange={(event) =>
                  setWizard((current) => ({
                    ...current,
                    smtp_config: {
                      ...current.smtp_config,
                      port: event.target.value ? Number(event.target.value) : null
                    }
                  }))
                }
                placeholder="587"
              />
            </label>
            <label className="field">
              <span>Username</span>
              <input
                value={wizard.smtp_config.username ?? ""}
                onChange={(event) =>
                  setWizard((current) => ({
                    ...current,
                    smtp_config: { ...current.smtp_config, username: event.target.value }
                  }))
                }
              />
            </label>
            <label className="field">
              <span>Password</span>
              <input
                type="password"
                value={smtpPassword}
                onChange={(event) => setSmtpPassword(event.target.value)}
                placeholder={
                  wizard.smtp_config.has_password
                    ? "Saved. Enter a new password to replace it."
                    : "SMTP password"
                }
              />
            </label>
            <label className="field">
              <span>From email</span>
              <input
                value={wizard.smtp_config.from_email ?? ""}
                onChange={(event) =>
                  setWizard((current) => ({
                    ...current,
                    smtp_config: { ...current.smtp_config, from_email: event.target.value }
                  }))
                }
                placeholder="pantry@example.com"
              />
            </label>
            <label className="field">
              <span>From name</span>
              <input
                value={wizard.smtp_config.from_name ?? ""}
                onChange={(event) =>
                  setWizard((current) => ({
                    ...current,
                    smtp_config: { ...current.smtp_config, from_name: event.target.value }
                  }))
                }
                placeholder="Pantry"
              />
            </label>
            <label className="field">
              <span>Security</span>
              <select
                value={wizard.smtp_config.security ?? "starttls"}
                onChange={(event) =>
                  setWizard((current) => ({
                    ...current,
                    smtp_config: { ...current.smtp_config, security: event.target.value }
                  }))
                }
              >
                <option value="starttls">STARTTLS</option>
                <option value="ssl">SSL</option>
                <option value="none">None</option>
              </select>
            </label>
          </div>
        </section>
      );
    }

    return (
      <section className="setup-step-card" data-testid="setup-review-step">
        <p className="eyebrow">Step 8</p>
        <h1>Review and complete</h1>
        <p className="step-copy">
          Check the staged data, jump back to anything you want to edit, then finalize the install
          in one controlled commit.
        </p>

        <div className="review-grid">
          <article className="review-card">
            <div className="setup-card-toolbar">
              <strong>Users</strong>
              <button type="button" className="ghost-button" onClick={() => moveToStep("users")}>
                Edit
              </button>
            </div>
            <p>{summarizeUser(wizard.admin_user)}</p>
            {wizard.initial_users.map((user) => (
              <p key={user.stage_id}>{summarizeUser(user)}</p>
            ))}
          </article>
          <article className="review-card">
            <div className="setup-card-toolbar">
              <strong>Household</strong>
              <button type="button" className="ghost-button" onClick={() => moveToStep("household")}>
                Edit
              </button>
            </div>
            <p>{wizard.household_name}</p>
            <p>
              {wizard.location_group_name}: {wizard.storage_locations.join(", ")}
            </p>
          </article>
          <article className="review-card">
            <div className="setup-card-toolbar">
              <strong>Public URL</strong>
              <button type="button" className="ghost-button" onClick={() => moveToStep("public_url")}>
                Edit
              </button>
            </div>
            <p>{wizard.public_base_url}</p>
          </article>
          <article className="review-card">
            <div className="setup-card-toolbar">
              <strong>Dietary preferences</strong>
              <button type="button" className="ghost-button" onClick={() => moveToStep("dietary")}>
                Edit
              </button>
            </div>
            <p>{wizard.household_dietary_preferences.join(", ") || "None staged"}</p>
          </article>
          <article className="review-card">
            <div className="setup-card-toolbar">
              <strong>AI</strong>
              <button type="button" className="ghost-button" onClick={() => moveToStep("ai")}>
                Edit
              </button>
            </div>
            <p>
              {wizard.ai_config.is_enabled
                ? `${wizard.ai_config.provider_type} · ${wizard.ai_config.base_url} · ${wizard.ai_config.default_model}`
                : "Skipped for now"}
            </p>
          </article>
          <article className="review-card">
            <div className="setup-card-toolbar">
              <strong>SMTP</strong>
              <button type="button" className="ghost-button" onClick={() => moveToStep("smtp")}>
                Edit
              </button>
            </div>
            <p>
              {wizard.smtp_config.is_enabled
                ? `${wizard.smtp_config.host}:${wizard.smtp_config.port ?? ""}`
                : "Skipped for now"}
            </p>
          </article>
        </div>

        {wizard.missing_requirements.length > 0 ? (
          <div className="setup-alert is-error">
            <strong>Complete these required items before finalizing:</strong>
            <ul>
              {wizard.missing_requirements.map((requirement) => (
                <li key={requirement}>{requirement}</li>
              ))}
            </ul>
          </div>
        ) : (
          <div className="setup-alert">
            <strong>Ready to finalize.</strong>
            <p>
              Pantry will create users, the first household, memberships, locations, settings, and
              any optional integrations in one final step.
            </p>
          </div>
        )}
      </section>
    );
  };

  return (
    <div className="setup-wizard-shell" data-testid="setup-wizard">
      <aside className="setup-sidebar panel">
        <p className="eyebrow">Pantry Setup</p>
        <h2>First-run wizard</h2>
        <p className="sidebar-copy">
          Build the install now, then finalize once everything looks right.
        </p>
        <SetupProgress steps={wizard.status.steps} currentStep={currentStep} onJump={moveToStep} />
      </aside>

      <div className="setup-main">
        {statusMessage ? <p className="status-note">{statusMessage}</p> : null}
        {error ? <p className="error-text">{error}</p> : null}
        {renderStep()}

        <div className="wizard-actions">
          <button
            type="button"
            className="ghost-button"
            disabled={currentStep === "welcome" || isSaving}
            onClick={() => moveToStep(previousStep(currentStep))}
          >
            Back
          </button>
          {currentStep === "review" ? (
            <button
              type="button"
              className="primary-button"
              disabled={isSaving || !wizard.can_complete}
              onClick={handleCompleteSetup}
            >
              {isSaving ? "Completing..." : "Complete Setup"}
            </button>
          ) : (
            <button
              type="button"
              className="primary-button"
              disabled={isSaving}
              onClick={handleNext}
            >
              {isSaving ? "Saving..." : "Next"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

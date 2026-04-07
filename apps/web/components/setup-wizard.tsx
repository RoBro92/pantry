"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useRef, useState } from "react";
import type {
  SetupStatusResponse,
  SetupWizardAssignmentSummary,
  SetupWizardDietaryUserSummary,
  SetupWizardStateResponse,
  SetupWizardUserSummary,
  SessionResponse
} from "../lib/api-types";
import { getHouseholdRoleLabel, type HouseholdRole } from "../lib/role-labels";
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

type AutoCapitalizeMode = "none" | "sentences" | "words" | "characters";
type AutoCorrectMode = "off" | "on";

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
const OPTIONAL_STEPS = new Set<SetupStepKey>(["public_url", "dietary", "ai", "smtp"]);

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
const EMPTY_PASSWORD_DRAFT: PasswordDraft = {
  password: "",
  confirm: ""
};

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
  if (!user.login && user.display_name) {
    return user.display_name;
  }
  if (!user.login) {
    return "Staged user";
  }
  return user.display_name ? `${user.display_name} (${user.login})` : user.login;
}

function renderSavedPasswordHint(user: SetupWizardUserSummary) {
  return user.password_saved ? "Password saved" : "Password not saved yet";
}

function buildAutocomplete(section: string, field: string) {
  return `section-${section} ${field}`;
}

function normalizeLoginKey(login: string) {
  return login.trim().toLowerCase();
}

function getPasswordDraftError(draft: PasswordDraft) {
  const hasInput = Boolean(draft.password || draft.confirm);
  if (!hasInput) {
    return null;
  }
  if (draft.password !== draft.confirm) {
    return "Password confirmation must match.";
  }
  if (draft.password.length < 8) {
    return "Passwords must be at least 8 characters.";
  }
  return null;
}

function getPersistablePassword(draft: PasswordDraft | undefined) {
  if (!draft) {
    return null;
  }
  if (getPasswordDraftError(draft)) {
    return null;
  }
  return draft.password ? draft.password : null;
}

function getUsersStepValidation(
  wizard: SetupWizardStateResponse,
  adminPasswordDraft: PasswordDraft,
  userPasswordDrafts: Record<string, PasswordDraft>
) {
  const loginCounts = new Map<string, number>();
  for (const user of [wizard.admin_user, ...wizard.initial_users]) {
    const key = normalizeLoginKey(user.login);
    if (!key) {
      continue;
    }
    loginCounts.set(key, (loginCounts.get(key) ?? 0) + 1);
  }

  let adminMessage: string | null = null;
  const adminLoginKey = normalizeLoginKey(wizard.admin_user.login);
  if (!adminLoginKey) {
    adminMessage = "Enter a username or email for the platform admin.";
  } else if ((loginCounts.get(adminLoginKey) ?? 0) > 1) {
    adminMessage = "Each staged user must have a unique username or email.";
  } else {
    adminMessage = getPasswordDraftError(adminPasswordDraft);
    if (!adminMessage && !wizard.admin_user.password_saved && !adminPasswordDraft.password) {
      adminMessage = "Add a password of at least 8 characters before continuing.";
    }
  }

  const additionalMessages: Record<string, string | null> = {};
  for (const user of wizard.initial_users) {
    const loginKey = normalizeLoginKey(user.login);
    let message: string | null = null;
    if (!loginKey) {
      message = "Add a username or email, or remove this staged user before continuing.";
    } else if ((loginCounts.get(loginKey) ?? 0) > 1) {
      message = "Each staged user must have a unique username or email.";
    } else {
      message = getPasswordDraftError(userPasswordDrafts[user.stage_id] ?? EMPTY_PASSWORD_DRAFT);
      if (!message && !user.password_saved && !userPasswordDrafts[user.stage_id]?.password) {
        message = "Add a password of at least 8 characters, or remove this user before continuing.";
      }
    }
    additionalMessages[user.stage_id] = message;
  }

  const firstMessage =
    adminMessage ??
    wizard.initial_users.map((user) => additionalMessages[user.stage_id]).find(Boolean) ??
    null;

  return {
    adminMessage,
    additionalMessages,
    canContinue: !adminMessage && Object.values(additionalMessages).every((message) => !message),
    firstMessage
  };
}

function PasswordFields({
  label,
  draft,
  onChange,
  onBlur,
  passwordName,
  confirmName,
  autoCompleteSection
}: {
  label: string;
  draft: PasswordDraft;
  onChange: (nextDraft: PasswordDraft) => void;
  onBlur?: () => void;
  passwordName: string;
  confirmName: string;
  autoCompleteSection: string;
}) {
  return (
    <div className="content-grid">
      <label className="field">
        <span>{label}</span>
        <input
          type="password"
          name={passwordName}
          value={draft.password}
          minLength={8}
          autoComplete={buildAutocomplete(autoCompleteSection, "new-password")}
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
          onChange={(event) => onChange({ ...draft, password: event.target.value })}
          onBlur={onBlur}
          placeholder="At least 8 characters"
        />
      </label>
      <label className="field">
        <span>Confirm password</span>
        <input
          type="password"
          name={confirmName}
          value={draft.confirm}
          minLength={8}
          autoComplete={buildAutocomplete(autoCompleteSection, "new-password")}
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
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
  placeholder,
  inputName,
  inputType = "text",
  autoComplete = "off",
  autoCapitalize = "words",
  autoCorrect = "off",
  inputMode,
  spellCheck = false
}: {
  tokens: string[];
  suggestions: string[];
  newValue: string;
  onNewValueChange: (value: string) => void;
  onAddToken: (value: string) => void;
  onRemoveToken: (value: string) => void;
  label: string;
  placeholder: string;
  inputName: string;
  inputType?: "text" | "url";
  autoComplete?: string;
  autoCapitalize?: AutoCapitalizeMode;
  autoCorrect?: AutoCorrectMode;
  inputMode?: "text" | "search" | "email" | "url" | "numeric" | "decimal";
  spellCheck?: boolean;
}) {
  return (
    <div className="stack">
      <label className="field">
        <span>{label}</span>
        <div className="token-input-row">
          <input
            type={inputType}
            name={inputName}
            value={newValue}
            autoComplete={autoComplete}
            autoCapitalize={autoCapitalize}
            autoCorrect={autoCorrect}
            inputMode={inputMode}
            spellCheck={spellCheck}
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
  const [adminPasswordDraft, setAdminPasswordDraft] = useState<PasswordDraft>(EMPTY_PASSWORD_DRAFT);
  const [userPasswordDrafts, setUserPasswordDrafts] = useState<Record<string, PasswordDraft>>({});
  const [newLocation, setNewLocation] = useState("");
  const [newHouseholdDietaryPreference, setNewHouseholdDietaryPreference] = useState("");
  const [newUserDietaryPreference, setNewUserDietaryPreference] = useState<Record<string, string>>({});
  const [aiApiKey, setAiApiKey] = useState("");
  const [smtpPassword, setSmtpPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const saveCounterRef = useRef(0);
  const latestAppliedSaveIdRef = useRef(0);

  const allUsers = [wizard.admin_user, ...wizard.initial_users];
  const configuredUsers = allUsers.filter((user) => Boolean(user.login.trim()));
  const usersValidation = getUsersStepValidation(wizard, adminPasswordDraft, userPasswordDrafts);
  const canSkipCurrentStep = OPTIONAL_STEPS.has(currentStep);

  function moveToStep(step: SetupStepKey) {
    setCurrentStep(step);
    const params = new URLSearchParams(searchParams.toString());
    params.set("step", step);
    router.replace(`/setup?${params.toString()}`, { scroll: false });
  }

  function updateWizard(
    nextState: SetupWizardStateResponse,
    savedMessage?: string,
    saveId?: number
  ) {
    if (saveId !== undefined) {
      if (saveId < latestAppliedSaveIdRef.current) {
        return;
      }
      latestAppliedSaveIdRef.current = saveId;
    }
    setWizard(nextState);
    setError(null);
    setStatusMessage(savedMessage ?? "Progress saved.");
  }

  function clearSavedPasswordDrafts() {
    const adminPassword = getPersistablePassword(adminPasswordDraft);
    if (adminPassword) {
      setAdminPasswordDraft(EMPTY_PASSWORD_DRAFT);
    }
    setUserPasswordDrafts((current) =>
      Object.fromEntries(
        Object.entries(current).filter(([, draft]) => !getPersistablePassword(draft))
      )
    );
  }

  async function persistUsersSnapshot(
    snapshot: SetupWizardStateResponse,
    options?: { suppressErrors?: boolean; clearPasswordDrafts?: boolean; saveId?: number }
  ) {
    const suppressErrors = Boolean(options?.suppressErrors);
    const validation = getUsersStepValidation(snapshot, adminPasswordDraft, userPasswordDrafts);
    if (!suppressErrors && !validation.canContinue) {
      setError(validation.firstMessage);
      return false;
    }

    updateWizard(
      await putToApi<SetupWizardStateResponse>("/api/setup/wizard/users", {
        admin_login: snapshot.admin_user.login,
        admin_display_name: snapshot.admin_user.display_name,
        admin_password: getPersistablePassword(adminPasswordDraft),
        initial_users: snapshot.initial_users.map((user) => ({
          stage_id: user.stage_id,
          login: user.login,
          display_name: user.display_name,
          password: getPersistablePassword(userPasswordDrafts[user.stage_id])
        }))
      }),
      "Users saved.",
      options?.saveId
    );

    if (options?.clearPasswordDrafts) {
      clearSavedPasswordDrafts();
    }
    return true;
  }

  async function persistHouseholdSnapshot(snapshot: SetupWizardStateResponse) {
    const saveId = ++saveCounterRef.current;
    try {
      updateWizard(
        await putToApi<SetupWizardStateResponse>("/api/setup/wizard/household", {
          household_name: snapshot.household_name ?? "",
          location_group_name: snapshot.location_group_name ?? "",
          storage_locations: snapshot.storage_locations,
          household_assignments: snapshot.household_assignments
        }),
        "Household details saved.",
        saveId
      );
    } catch {
      // Keep inline interaction resilient; the explicit Next save still surfaces errors.
    }
  }

  async function persistDietarySnapshot(snapshot: SetupWizardStateResponse) {
    const saveId = ++saveCounterRef.current;
    try {
      updateWizard(
        await putToApi<SetupWizardStateResponse>("/api/setup/wizard/dietary", {
          household_preferences: snapshot.household_dietary_preferences,
          user_preferences: snapshot.user_dietary_preferences
        }),
        "Dietary preferences saved.",
        saveId
      );
    } catch {
      // Keep inline interaction resilient; the explicit Next save still surfaces errors.
    }
  }

  async function persistStep(
    step: SetupStepKey,
    options?: {
      suppressErrors?: boolean;
      clearPasswordDrafts?: boolean;
      stateSnapshot?: SetupWizardStateResponse;
      aiApiKeyOverride?: string;
      smtpPasswordOverride?: string;
    }
  ): Promise<boolean> {
    const suppressErrors = Boolean(options?.suppressErrors);
    const snapshot = options?.stateSnapshot ?? wizard;
    const saveId = ++saveCounterRef.current;

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
          "Welcome step saved.",
          saveId
        );
      }

      if (step === "users") {
        return await persistUsersSnapshot(snapshot, {
          suppressErrors,
          clearPasswordDrafts: options?.clearPasswordDrafts ?? true,
          saveId
        });
      }

      if (step === "household") {
        updateWizard(
          await putToApi<SetupWizardStateResponse>("/api/setup/wizard/household", {
            household_name: snapshot.household_name ?? "",
            location_group_name: snapshot.location_group_name ?? "",
            storage_locations: snapshot.storage_locations,
            household_assignments: snapshot.household_assignments
          }),
          "Household details saved.",
          saveId
        );
      }

      if (step === "public_url") {
        updateWizard(
          await putToApi<SetupWizardStateResponse>("/api/setup/wizard/public-url", {
            public_base_url: snapshot.public_base_url ?? ""
          }),
          "Public browser URL saved.",
          saveId
        );
      }

      if (step === "dietary") {
        updateWizard(
          await putToApi<SetupWizardStateResponse>("/api/setup/wizard/dietary", {
            household_preferences: snapshot.household_dietary_preferences,
            user_preferences: snapshot.user_dietary_preferences
          }),
          "Dietary preferences saved.",
          saveId
        );
      }

      if (step === "ai") {
        updateWizard(
          await putToApi<SetupWizardStateResponse>("/api/setup/wizard/ai", {
            provider_type: snapshot.ai_config.provider_type,
            base_url: snapshot.ai_config.base_url,
            default_model: snapshot.ai_config.default_model,
            api_key: (options?.aiApiKeyOverride ?? aiApiKey) || null,
            is_enabled: snapshot.ai_config.is_enabled
          }),
          "AI settings saved.",
          saveId
        );
        setAiApiKey("");
      }

      if (step === "smtp") {
        updateWizard(
          await putToApi<SetupWizardStateResponse>("/api/setup/wizard/smtp", {
            host: snapshot.smtp_config.host,
            port: snapshot.smtp_config.port,
            username: snapshot.smtp_config.username,
            password: (options?.smtpPasswordOverride ?? smtpPassword) || null,
            from_email: snapshot.smtp_config.from_email,
            from_name: snapshot.smtp_config.from_name,
            security: snapshot.smtp_config.security,
            is_enabled: snapshot.smtp_config.is_enabled
          }),
          "SMTP settings saved.",
          saveId
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

  async function handleBack() {
    await persistStep(currentStep, { suppressErrors: true, clearPasswordDrafts: true });
    moveToStep(previousStep(currentStep));
  }

  async function handleStepJump(step: SetupStepKey) {
    if (step === currentStep) {
      return;
    }
    await persistStep(currentStep, { suppressErrors: true, clearPasswordDrafts: true });
    moveToStep(step);
  }

  async function handleSkip() {
    if (!OPTIONAL_STEPS.has(currentStep)) {
      return;
    }

    const nextWizard =
      currentStep === "public_url"
        ? { ...wizard, public_base_url: "" }
        : currentStep === "dietary"
          ? {
              ...wizard,
              household_dietary_preferences: [],
              user_dietary_preferences: []
            }
          : currentStep === "ai"
            ? {
                ...wizard,
                ai_config: {
                  provider_type: null,
                  base_url: "",
                  default_model: "",
                  is_enabled: false,
                  has_api_key: false
                }
              }
            : {
                ...wizard,
                smtp_config: {
                  host: "",
                  port: null,
                  username: "",
                  has_password: false,
                  from_email: "",
                  from_name: "",
                  security: null,
                  is_enabled: false
                }
              };

    const saved = await persistStep(currentStep, {
      stateSnapshot: nextWizard,
      aiApiKeyOverride: "",
      smtpPasswordOverride: "",
      clearPasswordDrafts: true
    });
    if (saved) {
      setAiApiKey("");
      setSmtpPassword("");
      moveToStep(nextStep(currentStep));
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
    const nextWizard = {
      ...wizard,
      initial_users: [
        ...wizard.initial_users,
        {
          stage_id: createStageId(),
          login: "",
          display_name: "",
          password_saved: false,
          is_platform_admin: false
        }
      ]
    };
    setWizard(nextWizard);
    void persistStep("users", {
      suppressErrors: true,
      clearPasswordDrafts: false,
      stateSnapshot: nextWizard
    });
  }

  function removeInitialUser(stageId: string) {
    const nextWizard = {
      ...wizard,
      initial_users: wizard.initial_users.filter((user) => user.stage_id !== stageId),
      household_assignments: wizard.household_assignments.filter(
        (assignment) => assignment.stage_user_id !== stageId
      ),
      user_dietary_preferences: wizard.user_dietary_preferences.filter(
        (preference) => preference.stage_user_id !== stageId
      )
    };
    setWizard(nextWizard);
    setUserPasswordDrafts((current) => {
      const nextDrafts = { ...current };
      delete nextDrafts[stageId];
      return nextDrafts;
    });
    void persistStep("users", {
      suppressErrors: true,
      clearPasswordDrafts: false,
      stateSnapshot: nextWizard
    });
  }

  function updateHouseholdAssignment(stageUserId: string, role: HouseholdRole | "none") {
    const nextWizard = {
      ...wizard,
      household_assignments:
        role === "none"
          ? wizard.household_assignments.filter(
              (assignment) => assignment.stage_user_id !== stageUserId
            )
          : [
              ...wizard.household_assignments.filter(
                (assignment) => assignment.stage_user_id !== stageUserId
              ),
              {
                stage_user_id: stageUserId,
                role
              }
            ]
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
          <h1>Complete Pantry setup once to proceed to dashboard</h1>
          <p className="lede compact">
            Follow the guided setup to create Users, a Household, and other key details. You can always adjust these later, but this will get you up and running with the best experience out of the box.
          </p>
          <div className="setup-highlight-grid">
            <article className="setup-highlight">
              <strong>Create Users</strong>
              <p>Create your primary platform user and then add additional household users with individual dietary preferences.</p>
            </article>
            <article className="setup-highlight">
              <strong>AI Integration</strong>
              <p>Currently supports Ollama and OpenAI API integrations for smart recipe suggestions based on pantry contents</p>
            </article>
            <article className="setup-highlight">
              <strong>SMTP Setup</strong>
              <p>Optional SMTP setup for emailed shopping lists, password resets and notifications</p>
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
            Create the main Pantry admin first, then stage any additional users you want available
            as soon as setup finishes.
          </p>

          <div className="setup-subsection">
            <div className="setup-subsection-heading">
              <h2>Platform admin</h2>
              <span className="pill is-required">Required</span>
            </div>
            <div className="content-grid">
              <label className="field">
                <span>Username or email</span>
                <input
                  type="text"
                  name="setup_admin_login"
                  value={wizard.admin_user.login}
                  autoComplete={buildAutocomplete("setup-admin", "username")}
                  autoCapitalize="none"
                  autoCorrect="off"
                  spellCheck={false}
                  onChange={(event) => updateAdmin({ login: event.target.value })}
                  onBlur={() =>
                    void persistStep("users", { suppressErrors: true, clearPasswordDrafts: false })
                  }
                  placeholder="owner"
                />
              </label>
              <label className="field">
                <span>Display name</span>
                <input
                  type="text"
                  name="setup_admin_display_name"
                  value={wizard.admin_user.display_name ?? ""}
                  autoComplete={buildAutocomplete("setup-admin", "name")}
                  autoCapitalize="words"
                  autoCorrect="off"
                  spellCheck={false}
                  onChange={(event) => updateAdmin({ display_name: event.target.value })}
                  onBlur={() =>
                    void persistStep("users", { suppressErrors: true, clearPasswordDrafts: false })
                  }
                  placeholder="Pantry owner"
                />
              </label>
            </div>
            <PasswordFields
              label={wizard.admin_user.password_saved ? "Replace password" : "Password"}
              draft={adminPasswordDraft}
              onChange={setAdminPasswordDraft}
              passwordName="setup_admin_password"
              confirmName="setup_admin_confirm_password"
              autoCompleteSection="setup-admin"
              onBlur={() =>
                void persistStep("users", { suppressErrors: true, clearPasswordDrafts: true })
              }
            />
            <p
              className={`helper-text${usersValidation.adminMessage ? " is-error" : ""}`}
              data-testid="setup-admin-password-status"
            >
              {usersValidation.adminMessage ?? renderSavedPasswordHint(wizard.admin_user)}
            </p>
          </div>

          <div className="setup-subsection">
            <div className="setup-subsection-heading">
              <h2>Additional users</h2>
              <button type="button" className="ghost-button" onClick={addInitialUser}>
                Add additional user
              </button>
            </div>
            <div className="stack">
              {wizard.initial_users.length === 0 ? (
                <div className="empty-state">
                  <p>
                    No extra users staged yet. Add as many people as you want now, or leave this
                    section empty and invite them later.
                  </p>
                </div>
              ) : null}
              {wizard.initial_users.map((user, index) => (
                <article
                  key={user.stage_id}
                  className="setup-user-card"
                  data-testid={`setup-user-card-${index + 1}`}
                >
                  <div className="setup-card-toolbar">
                    <strong>Additional user {index + 1}</strong>
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
                        type="text"
                        name={`setup_user_${user.stage_id}_login`}
                        value={user.login}
                        autoComplete={buildAutocomplete(`setup-user-${user.stage_id}`, "username")}
                        autoCapitalize="none"
                        autoCorrect="off"
                        spellCheck={false}
                        onChange={(event) =>
                          updateInitialUser(user.stage_id, { login: event.target.value })
                        }
                        onBlur={() =>
                          void persistStep("users", {
                            suppressErrors: true,
                            clearPasswordDrafts: false
                          })
                        }
                        placeholder="alex"
                      />
                    </label>
                    <label className="field">
                      <span>Display name</span>
                      <input
                        type="text"
                        name={`setup_user_${user.stage_id}_display_name`}
                        value={user.display_name ?? ""}
                        autoComplete={buildAutocomplete(`setup-user-${user.stage_id}`, "name")}
                        autoCapitalize="words"
                        autoCorrect="off"
                        spellCheck={false}
                        onChange={(event) =>
                          updateInitialUser(user.stage_id, { display_name: event.target.value })
                        }
                        onBlur={() =>
                          void persistStep("users", {
                            suppressErrors: true,
                            clearPasswordDrafts: false
                          })
                        }
                        placeholder="Alex"
                      />
                    </label>
                  </div>
                  <PasswordFields
                    label={user.password_saved ? "Replace password" : "Password"}
                    draft={userPasswordDrafts[user.stage_id] ?? EMPTY_PASSWORD_DRAFT}
                    onChange={(draft) =>
                      setUserPasswordDrafts((current) => ({ ...current, [user.stage_id]: draft }))
                    }
                    passwordName={`setup_user_${user.stage_id}_password`}
                    confirmName={`setup_user_${user.stage_id}_confirm_password`}
                    autoCompleteSection={`setup-user-${user.stage_id}`}
                    onBlur={() =>
                      void persistStep("users", { suppressErrors: true, clearPasswordDrafts: true })
                    }
                  />
                  <p className="helper-text">Assign this user’s household role in the next step.</p>
                  <p
                    className={`helper-text${
                      usersValidation.additionalMessages[user.stage_id] ? " is-error" : ""
                    }`}
                  >
                    {usersValidation.additionalMessages[user.stage_id] ??
                      renderSavedPasswordHint(user)}
                  </p>
                </article>
              ))}
            </div>
          </div>
        </section>
      );
    }

    if (currentStep === "household") {
      return (
        <section className="setup-step-card" data-testid="setup-household-step">
          <p className="eyebrow">Step 3</p>
          <h1>Household and storage locations</h1>
          <p className="step-copy">
            Create the first household, select the storage locations you want available,
            and choose who belongs to it.
          </p>

          <div className="content-grid">
            <label className="field">
              <span>Household name</span>
              <input
                type="text"
                name="setup_household_name"
                value={wizard.household_name ?? ""}
                autoComplete="organization"
                autoCapitalize="words"
                autoCorrect="off"
                spellCheck={false}
                onChange={(event) =>
                  setWizard((current) => ({ ...current, household_name: event.target.value }))
                }
                onBlur={() => void persistStep("household", { suppressErrors: true })}
                placeholder="household"
              />
            </label>
            <label className="field">
              <span>Default storage location</span>
              <input
                type="text"
                name="setup_location_group_name"
                value={wizard.location_group_name ?? ""}
                autoComplete="off"
                autoCapitalize="words"
                autoCorrect="off"
                spellCheck={false}
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
            label="Additional storage locations"
            placeholder="Add a storage location"
            inputName="setup_storage_location"
          />

          <div className="setup-subsection">
            <div className="setup-subsection-heading">
              <h2>Who should belong to this household?</h2>
            </div>
            <div className="stack">
              {configuredUsers.map((user) => {
                const assignment = findAssignment(wizard.household_assignments, user.stage_id);
                const isAdmin = user.is_platform_admin;
                return (
                  <article key={user.stage_id} className="setup-assignment-card">
                    <div className="setup-card-toolbar">
                      <strong>{summarizeUser(user)}</strong>
                      {isAdmin ? <span className="pill">Required</span> : null}
                    </div>
                    <label className="field">
                      <span>Membership</span>
                      <select
                        name={`setup_household_assignment_${user.stage_id}`}
                        aria-label={`Household membership for ${summarizeUser(user)}`}
                        disabled={isAdmin}
                        value={isAdmin ? "household_admin" : assignment?.role ?? "none"}
                        onChange={(event) =>
                          updateHouseholdAssignment(
                            user.stage_id,
                            event.target.value as HouseholdRole | "none"
                          )
                        }
                      >
                        {isAdmin ? null : <option value="none">Not assigned</option>}
                        <option value="household_admin">{getHouseholdRoleLabel("household_admin")}</option>
                        {!isAdmin ? (
                          <option value="household_user">{getHouseholdRoleLabel("household_user")}</option>
                        ) : null}
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
            will actually open personal devices.
          </p>
          <label className="field">
            <span>Public Pantry URL</span>
            <input
              type="url"
              name="setup_public_base_url"
              value={wizard.public_base_url ?? ""}
              autoComplete="url"
              autoCapitalize="none"
              autoCorrect="off"
              inputMode="url"
              spellCheck={false}
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
          <p className="helper-text">
            Optional. Skip this for now if you want Pantry to use the deployment default until you
            decide on a permanent address.
          </p>
        </section>
      );
    }

    if (currentStep === "dietary") {
      return (
        <section className="setup-step-card">
          <p className="eyebrow">Step 5</p>
          <h1>Dietary preferences</h1>
          <p className="step-copy">
            Select household dietary preferences and assign individual preferences to users. This will help Pantry make better meal suggestions and warnings about expiring goods.
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
            inputName="setup_household_dietary_preference"
          />

          <div className="setup-subsection">
            <div className="setup-subsection-heading">
              <h2>Optional individual preferences</h2>
            </div>
            <div className="stack">
              {configuredUsers.map((user) => (
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
                    inputName={`setup_user_${user.stage_id}_dietary_preference`}
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
            Optional. Configure Pantry’s instance level AI provider now if you want meal and pantry
            suggestions ready after setup.
          </p>
          <label className="checkbox-row">
            <input
              type="checkbox"
              name="setup_ai_enabled"
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
                name="setup_ai_provider_type"
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
                type="url"
                name="setup_ai_base_url"
                value={wizard.ai_config.base_url ?? ""}
                autoComplete="url"
                autoCapitalize="none"
                autoCorrect="off"
                inputMode="url"
                spellCheck={false}
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
                type="text"
                name="setup_ai_default_model"
                value={wizard.ai_config.default_model ?? ""}
                autoComplete="off"
                autoCapitalize="none"
                autoCorrect="off"
                spellCheck={false}
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
                name="setup_ai_api_key"
                value={aiApiKey}
                autoComplete="off"
                autoCapitalize="none"
                autoCorrect="off"
                spellCheck={false}
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
              name="setup_smtp_enabled"
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
                type="text"
                name="setup_smtp_host"
                value={wizard.smtp_config.host ?? ""}
                autoComplete="off"
                autoCapitalize="none"
                autoCorrect="off"
                spellCheck={false}
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
                name="setup_smtp_port"
                value={wizard.smtp_config.port ?? ""}
                autoComplete="off"
                autoCapitalize="none"
                autoCorrect="off"
                inputMode="numeric"
                spellCheck={false}
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
                type="text"
                name="setup_smtp_username"
                value={wizard.smtp_config.username ?? ""}
                autoComplete="off"
                autoCapitalize="none"
                autoCorrect="off"
                spellCheck={false}
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
                name="setup_smtp_password"
                value={smtpPassword}
                autoComplete="off"
                autoCapitalize="none"
                autoCorrect="off"
                spellCheck={false}
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
                type="email"
                name="setup_smtp_from_email"
                value={wizard.smtp_config.from_email ?? ""}
                autoComplete="email"
                autoCapitalize="none"
                autoCorrect="off"
                inputMode="email"
                spellCheck={false}
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
                type="text"
                name="setup_smtp_from_name"
                value={wizard.smtp_config.from_name ?? ""}
                autoComplete="organization"
                autoCapitalize="words"
                autoCorrect="off"
                spellCheck={false}
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
                name="setup_smtp_security"
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
          Check everything looks right, then complete the setup. Pantry will only write this staged
          data into the live application once you confirm.
        </p>

        <div className="review-grid">
          <article className="review-card">
            <div className="setup-card-toolbar">
              <strong>Users</strong>
              <button type="button" className="ghost-button" onClick={() => void handleStepJump("users")}>
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
              <button
                type="button"
                className="ghost-button"
                onClick={() => void handleStepJump("household")}
              >
                Edit
              </button>
            </div>
            <p>{wizard.household_name || "Not configured yet"}</p>
            <p>
              {wizard.location_group_name}:{" "}
              {wizard.storage_locations.length > 0 ? wizard.storage_locations.join(", ") : "No storage locations yet"}
            </p>
            <p>
              Members:{" "}
              {configuredUsers
                .map((user) => {
                  if (user.is_platform_admin) {
                    return `${summarizeUser(user)} (${getHouseholdRoleLabel("household_admin")})`;
                  }
                  const assignment = findAssignment(wizard.household_assignments, user.stage_id);
                  if (!assignment) {
                    return null;
                  }
                  return `${summarizeUser(user)} (${getHouseholdRoleLabel(assignment.role)})`;
                })
                .filter(Boolean)
                .join(", ") || "No household members selected yet"}
            </p>
          </article>
          <article className="review-card">
            <div className="setup-card-toolbar">
              <strong>Public URL</strong>
              <button
                type="button"
                className="ghost-button"
                onClick={() => void handleStepJump("public_url")}
              >
                Edit
              </button>
            </div>
            <p>{wizard.public_base_url || "Skipped for now"}</p>
          </article>
          <article className="review-card">
            <div className="setup-card-toolbar">
              <strong>Dietary preferences</strong>
              <button
                type="button"
                className="ghost-button"
                onClick={() => void handleStepJump("dietary")}
              >
                Edit
              </button>
            </div>
            <p>
              {wizard.household_dietary_preferences.length > 0
                ? wizard.household_dietary_preferences.join(", ")
                : "Skipped for now"}
            </p>
            <p>
              Personal preferences:{" "}
              {wizard.user_dietary_preferences.length > 0
                ? wizard.user_dietary_preferences
                    .map((preference) => {
                      const user = allUsers.find(
                        (candidate) => candidate.stage_id === preference.stage_user_id
                      );
                      return `${user ? summarizeUser(user) : "Staged user"} (${preference.preferences.join(", ")})`;
                    })
                    .join(", ")
                : "Not configured"}
            </p>
          </article>
          <article className="review-card">
            <div className="setup-card-toolbar">
              <strong>AI</strong>
              <button type="button" className="ghost-button" onClick={() => void handleStepJump("ai")}>
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
              <button
                type="button"
                className="ghost-button"
                onClick={() => void handleStepJump("smtp")}
              >
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
        <SetupProgress
          steps={wizard.status.steps}
          currentStep={currentStep}
          onJump={(step) => void handleStepJump(step)}
        />
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
            onClick={() => void handleBack()}
          >
            Back
          </button>
          <div className="wizard-actions-group">
            {canSkipCurrentStep ? (
              <button
                type="button"
                className="ghost-button"
                disabled={isSaving}
                onClick={() => void handleSkip()}
              >
                Skip for now
              </button>
            ) : null}
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
                disabled={isSaving || (currentStep === "users" && !usersValidation.canContinue)}
                onClick={handleNext}
              >
                {isSaving ? "Saving..." : "Next"}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

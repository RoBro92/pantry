"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { type FormEvent, type ReactNode, useRef, useState } from "react";
import type {
  SetupStatusResponse,
  SetupWizardAssignmentSummary,
  SetupWizardDietaryUserSummary,
  SetupWizardRoomSummary,
  SetupWizardStateResponse,
  SetupWizardUserSummary,
  SessionResponse
} from "../lib/api-types";
import {
  AI_PROVIDER_API_KEY_REQUIRED,
  getAIProviderSupport,
  getDefaultBaseUrl,
  getDefaultModel,
  normalizeAIProviderType,
} from "../lib/ai-provider-config";
import { getHouseholdRoleLabel, type HouseholdRole } from "../lib/role-labels";
import { postFormToApi, postToApi, putToApi } from "../lib/client-api";
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

const OPTIONAL_STEPS = new Set<SetupStepKey>(["public_url", "dietary", "ai", "smtp"]);
const FRESH_INSTALL_STEPS: SetupStepKey[] = [
  "welcome",
  "users",
  "dietary",
  "household",
  "public_url",
  "ai",
  "smtp",
  "review"
];
const RESTORE_STEPS: SetupStepKey[] = ["welcome", "review"];

const LOCATION_SUGGESTIONS = ["Fridge", "Freezer", "Cupboard", "Pantry shelf"];
const DIETARY_SUGGESTIONS = [
  "None",
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
const DIETARY_NONE_OPTION = "None";

function getStepOrder(mode: SetupWizardStateResponse["installation_mode"]) {
  return mode === "restore_backup" ? RESTORE_STEPS : FRESH_INSTALL_STEPS;
}

function nextStep(currentStep: SetupStepKey, stepOrder: SetupStepKey[]): SetupStepKey {
  const currentIndex = stepOrder.indexOf(currentStep);
  return stepOrder[Math.min(currentIndex + 1, stepOrder.length - 1)];
}

function previousStep(currentStep: SetupStepKey, stepOrder: SetupStepKey[]): SetupStepKey {
  const currentIndex = stepOrder.indexOf(currentStep);
  return stepOrder[Math.max(currentIndex - 1, 0)];
}

function createStageId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `stage-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function getSetupAIProviderType(providerType: string | null | undefined): "openai" {
  const normalizedProviderType = normalizeAIProviderType(providerType);
  return normalizedProviderType === "openai" ? "openai" : "openai";
}

function createEmptyRoom(stageId = createStageId()): SetupWizardRoomSummary {
  return {
    stage_id: stageId,
    name: "",
    storage_locations: []
  };
}

function deriveLegacyRoomFields(rooms: SetupWizardRoomSummary[]) {
  const firstRoom = rooms[0];
  return {
    location_group_name: firstRoom?.name ?? "",
    storage_locations: firstRoom?.storage_locations ?? []
  };
}

function syncWizardRooms(
  wizard: SetupWizardStateResponse,
  rooms: SetupWizardRoomSummary[]
): SetupWizardStateResponse {
  const nextRooms = rooms.length > 0 ? rooms : [createEmptyRoom()];
  return {
    ...wizard,
    rooms: nextRooms,
    ...deriveLegacyRoomFields(nextRooms)
  };
}

function buildHouseholdPayload(snapshot: SetupWizardStateResponse) {
  const syncedSnapshot = syncWizardRooms(snapshot, snapshot.rooms);
  return {
    household_name: syncedSnapshot.household_name ?? "",
    rooms: syncedSnapshot.rooms.map((room) => ({
      stage_id: room.stage_id,
      name: room.name ?? "",
      storage_locations: room.storage_locations
    })),
    location_group_name: syncedSnapshot.location_group_name ?? "",
    storage_locations: syncedSnapshot.storage_locations,
    household_assignments: syncedSnapshot.household_assignments
  };
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

function normalizeDietarySelection(values: string[]) {
  const normalized = Array.from(new Set(values.map((value) => value.trim()).filter(Boolean)));
  return normalized.includes(DIETARY_NONE_OPTION)
    ? [DIETARY_NONE_OPTION]
    : normalized.filter((value) => value !== DIETARY_NONE_OPTION);
}

function addSkippedOptionalStep(
  steps: SetupWizardStateResponse["skipped_optional_steps"],
  step: SetupWizardStateResponse["skipped_optional_steps"][number]
) {
  return Array.from(new Set([...steps, step]));
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

function ensureSetupOpenAIConfig(aiConfig: SetupWizardStateResponse["ai_config"]) {
  return {
    ...aiConfig,
    provider_type: "openai" as const,
    base_url: aiConfig.base_url || getDefaultBaseUrl("openai"),
    default_model: aiConfig.default_model || getDefaultModel("openai")
  };
}

function getRestoreValidationIssues(wizard: SetupWizardStateResponse) {
  if (wizard.installation_mode !== "restore_backup") {
    return [];
  }
  if (!wizard.staged_restore) {
    return ["Upload and validate a full instance Pantry backup before continuing."];
  }
  if (wizard.staged_restore.supported_for_restore) {
    return [];
  }
  return wizard.staged_restore.warnings.length > 0
    ? wizard.staged_restore.warnings
    : ["This staged backup does not meet the current restore requirements."];
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

function ReviewSummaryCard({
  title,
  badge,
  onEdit,
  children,
}: {
  title: string;
  badge?: string;
  onEdit?: () => void;
  children: ReactNode;
}) {
  return (
    <article className="review-summary-card">
      <div className="setup-card-toolbar">
        <div className="stack compact-stack">
          <strong>{title}</strong>
          {badge ? <span className="pill">{badge}</span> : null}
        </div>
        {onEdit ? (
          <button type="button" className="ghost-button compact-button" onClick={onEdit}>
            Edit
          </button>
        ) : null}
      </div>
      <div className="review-summary-content">{children}</div>
    </article>
  );
}

function ReviewSummaryRow({
  label,
  value,
  wrap = false,
}: {
  label: string;
  value: React.ReactNode;
  wrap?: boolean;
}) {
  return (
    <div className="review-summary-row">
      <span className="review-summary-label">{label}</span>
      <span className={wrap ? "review-summary-value is-wrap" : "review-summary-value"}>{value}</span>
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
  const [expandedRoomStageId, setExpandedRoomStageId] = useState<string | null>(
    initialState.rooms[0]?.stage_id ?? null
  );
  const [newRoomLocations, setNewRoomLocations] = useState<Record<string, string>>({});
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
  const stepOrder = getStepOrder(wizard.installation_mode);
  const canSkipCurrentStep =
    wizard.installation_mode === "fresh_install" && OPTIONAL_STEPS.has(currentStep);
  const restoreValidationIssues = getRestoreValidationIssues(wizard);
  const restoreCannotContinue =
    currentStep === "welcome" &&
    wizard.installation_mode === "restore_backup" &&
    restoreValidationIssues.length > 0;

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
    if (!nextState.rooms.some((room) => room.stage_id === expandedRoomStageId)) {
      setExpandedRoomStageId(nextState.rooms[0]?.stage_id ?? null);
    }
    setError(null);
    setStatusMessage(savedMessage ?? "Progress saved.");
  }

  async function persistUsersSnapshot(
    snapshot: SetupWizardStateResponse,
    options?: { suppressErrors?: boolean; saveId?: number }
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
    return true;
  }

  async function persistHouseholdSnapshot(snapshot: SetupWizardStateResponse) {
    const saveId = ++saveCounterRef.current;
    try {
      updateWizard(
        await putToApi<SetupWizardStateResponse>(
          "/api/setup/wizard/household",
          buildHouseholdPayload(snapshot)
        ),
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
          user_preferences: snapshot.user_dietary_preferences,
          mark_skipped: snapshot.skipped_optional_steps.includes("dietary")
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
        if (
          snapshot.installation_mode === "restore_backup" &&
          !snapshot.staged_restore?.supported_for_restore
        ) {
          if (!suppressErrors) {
            setError(getRestoreValidationIssues(snapshot).join(" "));
          }
          return false;
        }
        await putToApi<SetupWizardStateResponse>("/api/setup/wizard/welcome", {
          acknowledged: true
        });
        updateWizard(
          await putToApi<SetupWizardStateResponse>("/api/setup/wizard/mode", {
            installation_mode: snapshot.installation_mode
          }),
          snapshot.installation_mode === "restore_backup"
            ? "Restore selection saved."
            : "Fresh install selected.",
          saveId
        );
      }

      if (step === "users") {
        return await persistUsersSnapshot(snapshot, {
          suppressErrors,
          saveId
        });
      }

      if (step === "household") {
        updateWizard(
          await putToApi<SetupWizardStateResponse>(
            "/api/setup/wizard/household",
            buildHouseholdPayload(snapshot)
          ),
          "Household details saved.",
          saveId
        );
      }

      if (step === "public_url") {
        updateWizard(
          await putToApi<SetupWizardStateResponse>("/api/setup/wizard/public-url", {
            public_base_url: snapshot.public_base_url ?? "",
            mark_skipped: snapshot.skipped_optional_steps.includes("public_url")
          }),
          "Public browser URL saved.",
          saveId
        );
      }

      if (step === "dietary") {
        updateWizard(
          await putToApi<SetupWizardStateResponse>("/api/setup/wizard/dietary", {
            household_preferences: snapshot.household_dietary_preferences,
            user_preferences: snapshot.user_dietary_preferences,
            mark_skipped: snapshot.skipped_optional_steps.includes("dietary")
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
            is_enabled: snapshot.ai_config.is_enabled,
            mark_skipped: snapshot.skipped_optional_steps.includes("ai")
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
            is_enabled: snapshot.smtp_config.is_enabled,
            password_reset_enabled: snapshot.smtp_config.password_reset_enabled,
            mark_skipped: snapshot.skipped_optional_steps.includes("smtp")
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
        moveToStep(nextStep(currentStep, stepOrder));
      }
    }
  }

  async function handleBack() {
    await persistStep(currentStep, { suppressErrors: true });
    moveToStep(previousStep(currentStep, stepOrder));
  }

  async function handleStepJump(step: SetupStepKey) {
    if (step === currentStep) {
      return;
    }
    await persistStep(currentStep, { suppressErrors: true });
    moveToStep(step);
  }

  async function handleSkip() {
    if (!OPTIONAL_STEPS.has(currentStep)) {
      return;
    }

    const nextWizard =
      currentStep === "public_url"
        ? {
            ...wizard,
            public_base_url: "",
            skipped_optional_steps: addSkippedOptionalStep(
              wizard.skipped_optional_steps,
              "public_url"
            )
          }
        : currentStep === "dietary"
          ? {
              ...wizard,
              skipped_optional_steps: addSkippedOptionalStep(
                wizard.skipped_optional_steps,
                "dietary"
              ),
              household_dietary_preferences: [],
              user_dietary_preferences: []
            }
          : currentStep === "ai"
            ? {
                ...wizard,
                skipped_optional_steps: addSkippedOptionalStep(
                  wizard.skipped_optional_steps,
                  "ai"
                ),
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
                skipped_optional_steps: addSkippedOptionalStep(
                  wizard.skipped_optional_steps,
                  "smtp"
                ),
                smtp_config: {
                  host: "",
                  port: null,
                  username: "",
                  has_password: false,
                  from_email: "",
                  from_name: "",
                  security: null,
                  is_enabled: false,
                  password_reset_enabled: false
                }
              };

    const saved = await persistStep(currentStep, {
      stateSnapshot: nextWizard,
      aiApiKeyOverride: "",
      smtpPasswordOverride: ""
    });
    if (saved) {
      setAiApiKey("");
      setSmtpPassword("");
      moveToStep(nextStep(currentStep, stepOrder));
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

  async function handleInstallModeChange(mode: SetupWizardStateResponse["installation_mode"]) {
    setError(null);
    setStatusMessage(null);
    setIsSaving(true);
    try {
      const nextState = await putToApi<SetupWizardStateResponse>("/api/setup/wizard/mode", {
        installation_mode: mode
      });
      updateWizard(
        nextState,
        mode === "restore_backup" ? "Restore mode selected." : "Fresh install selected."
      );
      if (!getStepOrder(mode).includes(currentStep)) {
        moveToStep("welcome");
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not update setup mode.");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleRestoreUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setStatusMessage(null);
    setIsSaving(true);
    try {
      const formData = new FormData(event.currentTarget);
      const nextState = await postFormToApi<SetupWizardStateResponse>(
        "/api/setup/wizard/restore-upload",
        formData
      );
      updateWizard(
        nextState,
        nextState.staged_restore?.supported_for_restore
          ? "Restore backup staged safely."
          : "Backup uploaded, but Pantry cannot restore it on this installation."
      );
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Restore upload failed.");
    } finally {
      setIsSaving(false);
    }
  }

  function addRoom() {
    const nextWizard = syncWizardRooms(wizard, [...wizard.rooms, createEmptyRoom()]);
    const nextRoom = nextWizard.rooms[nextWizard.rooms.length - 1];
    setWizard(nextWizard);
    setExpandedRoomStageId(nextRoom?.stage_id ?? null);
    void persistHouseholdSnapshot(nextWizard);
  }

  function removeRoom(stageId: string) {
    const remainingRooms = wizard.rooms.filter((room) => room.stage_id !== stageId);
    const nextWizard = syncWizardRooms(wizard, remainingRooms);
    setWizard(nextWizard);
    if (expandedRoomStageId === stageId) {
      setExpandedRoomStageId(nextWizard.rooms[0]?.stage_id ?? null);
    }
    setNewRoomLocations((current) => {
      const nextValues = { ...current };
      delete nextValues[stageId];
      return nextValues;
    });
    void persistHouseholdSnapshot(nextWizard);
  }

  function updateRoomName(stageId: string, value: string) {
    setWizard((current) =>
      syncWizardRooms(
        current,
        current.rooms.map((room) =>
          room.stage_id === stageId
            ? {
                ...room,
                name: value
              }
            : room
        )
      )
    );
  }

  function addStorageLocation(stageId: string, value: string) {
    const trimmed = value.trim();
    if (!trimmed) {
      return;
    }
    const nextWizard = syncWizardRooms(
      wizard,
      wizard.rooms.map((room) =>
        room.stage_id === stageId
          ? {
              ...room,
              storage_locations: Array.from(new Set([...room.storage_locations, trimmed]))
            }
          : room
      )
    );
    setWizard(nextWizard);
    setNewRoomLocations((current) => ({ ...current, [stageId]: "" }));
    void persistHouseholdSnapshot(nextWizard);
  }

  function removeStorageLocation(stageId: string, location: string) {
    const nextWizard = syncWizardRooms(
      wizard,
      wizard.rooms.map((room) =>
        room.stage_id === stageId
          ? {
              ...room,
              storage_locations: room.storage_locations.filter((item) => item !== location)
            }
          : room
      )
    );
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
      skipped_optional_steps: wizard.skipped_optional_steps.filter((step) => step !== "dietary"),
      household_dietary_preferences: normalizeDietarySelection([
        ...wizard.household_dietary_preferences,
        trimmed
      ])
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
    const nextPreferences = normalizeDietarySelection([...existing, trimmed]);
    const others = wizard.user_dietary_preferences.filter(
      (item) => item.stage_user_id !== stageUserId
    );
    const nextWizard = {
      ...wizard,
      skipped_optional_steps: wizard.skipped_optional_steps.filter((step) => step !== "dietary"),
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
        <section className="setup-step-card" data-testid="setup-install-selection-step">
          <p className="eyebrow">Step {stepOrder.indexOf("welcome") + 1}</p>
          <h1>Install selection</h1>
          <p className="step-copy">
            Choose how this Pantry instance should start. Pantry keeps everything staged until the
            final confirmation step so operators stay in control.
          </p>

          <div className="setup-highlight-grid install-selection-grid">
            <article className="setup-highlight install-selection-card">
              <strong>Fresh install</strong>
              <p>
                Create users, dietary preferences, rooms, storage locations, and optional
                integrations from scratch.
              </p>
              <div className="install-selection-actions">
                <button
                  type="button"
                  className={
                    wizard.installation_mode === "fresh_install" ? "primary-button" : "ghost-button"
                  }
                  onClick={() => void handleInstallModeChange("fresh_install")}
                  disabled={isSaving}
                >
                  {wizard.installation_mode === "fresh_install" ? "Selected" : "Choose fresh install"}
                </button>
              </div>
            </article>

            <article className="setup-highlight install-selection-card">
              <strong>Restore from backup</strong>
              <p>
                Upload a full instance backup bundle. Pantry validates it safely and restores it
                only when setup is finalized.
              </p>
              <div className="install-selection-actions">
                <button
                  type="button"
                  className={
                    wizard.installation_mode === "restore_backup" ? "primary-button" : "ghost-button"
                  }
                  onClick={() => void handleInstallModeChange("restore_backup")}
                  disabled={isSaving}
                >
                  {wizard.installation_mode === "restore_backup" ? "Selected" : "Choose restore"}
                </button>
              </div>
            </article>
          </div>

          {wizard.installation_mode === "fresh_install" ? (
            <div className="info-callout">
              <strong>Fresh install selected</strong>
              <p>
                Continue to create your platform admin, first household, dietary preferences, and
                optional instance settings.
              </p>
            </div>
          ) : (
            <div className="stack">
              <form className="stack" onSubmit={handleRestoreUpload}>
                <label className="field">
                  <span>Pantry backup bundle</span>
                  <input type="file" name="file" accept=".json,application/json" required />
                </label>
                <div className="page-actions">
                  <button type="submit" className="primary-button" disabled={isSaving}>
                    {isSaving ? "Uploading..." : "Upload and validate"}
                  </button>
                </div>
              </form>

              {wizard.staged_restore ? (
                <div className="stack">
                  <div
                    className={
                      wizard.staged_restore.supported_for_restore ? "info-callout" : "warning-callout"
                    }
                  >
                    <strong>
                      {wizard.staged_restore.supported_for_restore
                        ? "Staged restore bundle"
                        : "Restore blocked for this backup"}
                    </strong>
                    <p>
                      {wizard.staged_restore.original_filename} · {wizard.staged_restore.bundle.scope} · exported from Pantry {wizard.staged_restore.bundle.app_version}
                    </p>
                    <p>
                      {wizard.staged_restore.supported_for_restore
                        ? "Validated and ready to continue to review."
                        : "Pantry staged the file safely, but this backup does not meet the current restore requirements."}
                    </p>
                  </div>
                  <ul className="callout-list">
                    {wizard.staged_restore.warnings.map((warning) => (
                      <li key={warning}>{warning}</li>
                    ))}
                  </ul>
                </div>
              ) : (
                <div className="warning-callout">
                  <strong>Restore upload required</strong>
                  <p>Upload and validate a full instance Pantry backup before continuing.</p>
                </div>
              )}
            </div>
          )}
        </section>
      );
    }

    if (currentStep === "users") {
      return (
        <section className="setup-step-card" data-testid="setup-users-step">
          <p className="eyebrow">Step {stepOrder.indexOf("users") + 1}</p>
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
                  onBlur={() => void persistStep("users", { suppressErrors: true })}
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
                  onBlur={() => void persistStep("users", { suppressErrors: true })}
                  placeholder="Pantry owner"
                />
              </label>
            </div>
            <p className="helper-text">
              Use an email address if this account should be able to request its own password reset later.
            </p>
            <PasswordFields
              label={
                wizard.admin_user.password_saved && !adminPasswordDraft.password
                  ? "Replace password"
                  : "Password"
              }
              draft={adminPasswordDraft}
              onChange={setAdminPasswordDraft}
              passwordName="setup_admin_password"
              confirmName="setup_admin_confirm_password"
              autoCompleteSection="setup-admin"
              onBlur={() => void persistStep("users", { suppressErrors: true })}
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
                        onBlur={() => void persistStep("users", { suppressErrors: true })}
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
                        onBlur={() => void persistStep("users", { suppressErrors: true })}
                        placeholder="Alex"
                      />
                    </label>
                  </div>
                  <p className="helper-text">
                    Username-only accounts still need an admin-led password reset later.
                  </p>
                  <PasswordFields
                    label={
                      user.password_saved && !(userPasswordDrafts[user.stage_id] ?? EMPTY_PASSWORD_DRAFT).password
                        ? "Replace password"
                        : "Password"
                    }
                    draft={userPasswordDrafts[user.stage_id] ?? EMPTY_PASSWORD_DRAFT}
                    onChange={(draft) =>
                      setUserPasswordDrafts((current) => ({ ...current, [user.stage_id]: draft }))
                    }
                    passwordName={`setup_user_${user.stage_id}_password`}
                    confirmName={`setup_user_${user.stage_id}_confirm_password`}
                    autoCompleteSection={`setup-user-${user.stage_id}`}
                    onBlur={() => void persistStep("users", { suppressErrors: true })}
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
          <p className="eyebrow">Step {stepOrder.indexOf("household") + 1}</p>
          <h1>Create household and rooms</h1>
          <p className="step-copy">
            Create the primary household, multiple rooms with their storage locations, and
            choose who belongs to it.
          </p>

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
              placeholder="Your House"
            />
          </label>

          <div className="setup-subsection">
            <div className="setup-subsection-heading">
              <div className="stack compact-stack">
                <h2>Rooms and Storage</h2>
                <p className="helper-text">
                  Pantry uses Rooms for high level spaces such as Kitchen, Garage, or Utility room,
                  with storage locations inside each one.
                </p>
              </div>
              <button type="button" className="ghost-button" onClick={addRoom}>
                Add another Room
              </button>
            </div>

            <div className="setup-room-stack">
              {wizard.rooms.map((room, index) => {
                const isExpanded =
                  expandedRoomStageId === room.stage_id ||
                  (expandedRoomStageId === null && index === 0);
                const roomLabel = room.name?.trim() || `Room ${index + 1}`;
                return (
                  <article
                    key={room.stage_id}
                    className={`setup-room-card${isExpanded ? " is-expanded" : ""}`}
                    data-testid={`setup-room-card-${index + 1}`}
                  >
                    <div className="setup-room-header">
                      <button
                        type="button"
                        className="setup-room-toggle"
                        aria-expanded={isExpanded}
                        onClick={() =>
                          setExpandedRoomStageId(isExpanded ? null : room.stage_id)
                        }
                      >
                        <div className="stack compact-stack">
                          <span className="eyebrow">Room {index + 1}</span>
                          <strong>{roomLabel}</strong>
                          <p className="helper-text">
                            {room.storage_locations.length > 0
                              ? room.storage_locations.join(", ")
                              : "No storage locations yet"}
                          </p>
                        </div>
                      </button>
                      {wizard.rooms.length > 1 ? (
                        <button
                          type="button"
                          className="ghost-button compact-button"
                          onClick={() => removeRoom(room.stage_id)}
                        >
                          Remove Room
                        </button>
                      ) : (
                        <span className="pill">Required</span>
                      )}
                    </div>

                    {isExpanded ? (
                      <div className="setup-room-body">
                        <label className="field">
                          <span>Room name</span>
                          <input
                            type="text"
                            name={`setup_room_name_${room.stage_id}`}
                            value={room.name ?? ""}
                            autoComplete="off"
                            autoCapitalize="words"
                            autoCorrect="off"
                            spellCheck={false}
                            onChange={(event) =>
                              updateRoomName(room.stage_id, event.target.value)
                            }
                            onBlur={() => void persistStep("household", { suppressErrors: true })}
                            placeholder="Kitchen"
                          />
                        </label>

                        <TokenEditor
                          tokens={room.storage_locations}
                          suggestions={LOCATION_SUGGESTIONS}
                          newValue={newRoomLocations[room.stage_id] ?? ""}
                          onNewValueChange={(value) =>
                            setNewRoomLocations((current) => ({
                              ...current,
                              [room.stage_id]: value
                            }))
                          }
                          onAddToken={(value) => addStorageLocation(room.stage_id, value)}
                          onRemoveToken={(value) => removeStorageLocation(room.stage_id, value)}
                          label="Storage locations"
                          placeholder="Add a storage location such as Fridge"
                          inputName={`setup_storage_location_${room.stage_id}`}
                        />
                      </div>
                    ) : null}
                  </article>
                );
              })}
            </div>
          </div>

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
          <p className="eyebrow">Step {stepOrder.indexOf("public_url") + 1}</p>
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
                setWizard((current) => ({
                  ...current,
                  public_base_url: event.target.value,
                  skipped_optional_steps: current.skipped_optional_steps.filter(
                    (step) => step !== "public_url"
                  )
                }))
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
          <p className="eyebrow">Step {stepOrder.indexOf("dietary") + 1}</p>
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
      const selectedProviderType = getSetupAIProviderType(wizard.ai_config.provider_type);
      const providerSupport = getAIProviderSupport(selectedProviderType);
      return (
        <section className="setup-step-card">
          <p className="eyebrow">Step {stepOrder.indexOf("ai") + 1}</p>
          <h1>AI configuration</h1>
          <p className="step-copy">
            Optional. Configure Pantry’s instance level AI provider now if you want meal and pantry
            suggestions ready after setup.
          </p>
          <p className={`helper-text${providerSupport.isCurrentlySupported ? "" : " is-error"}`}>
            {providerSupport.statusLabel}. {providerSupport.description}
          </p>
          <label className="checkbox-row">
            <input
              type="checkbox"
              name="setup_ai_enabled"
              checked={wizard.ai_config.is_enabled}
              onChange={(event) =>
                setWizard((current) => ({
                  ...current,
                  skipped_optional_steps: current.skipped_optional_steps.filter(
                    (step) => step !== "ai"
                  ),
                  ai_config: event.target.checked
                    ? { ...ensureSetupOpenAIConfig(current.ai_config), is_enabled: true }
                    : { ...current.ai_config, is_enabled: false, provider_type: "openai" }
                }))
              }
            />
            <span>Enable AI suggestions for this Pantry instance.</span>
          </label>
          <div className="content-grid">
            <label className="field">
              <span>Provider</span>
              <div className="ai-provider-readonly-value" aria-label="Provider type">
                OpenAI
              </div>
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
                    skipped_optional_steps: current.skipped_optional_steps.filter(
                      (step) => step !== "ai"
                    ),
                    ai_config: {
                      ...ensureSetupOpenAIConfig(current.ai_config),
                      base_url: event.target.value
                    }
                  }))
                }
                placeholder={getDefaultBaseUrl(selectedProviderType)}
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
                    skipped_optional_steps: current.skipped_optional_steps.filter(
                      (step) => step !== "ai"
                    ),
                    ai_config: {
                      ...ensureSetupOpenAIConfig(current.ai_config),
                      default_model: event.target.value
                    }
                  }))
                }
                placeholder={getDefaultModel(selectedProviderType)}
              />
              <p className="helper-text">
                Recommended: <code>gpt-4.1-mini</code> for fastest low-cost runs,{" "}
                <code>gpt-5.4-mini</code> as Pantry&apos;s default balance, or <code>gpt-5.4</code>{" "}
                for the strongest quality.
              </p>
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
                    : AI_PROVIDER_API_KEY_REQUIRED[selectedProviderType]
                      ? "Required for this provider"
                      : "Not required for this provider"
                }
              />
            </label>
          </div>
          {!providerSupport.isCurrentlySupported ? (
            <p className="helper-text">
              Finish setup with OpenAI if you want Pantry’s AI classification and guided meal
              suggestions ready immediately. The other providers remain visible for future
              validation work.
            </p>
          ) : null}
        </section>
      );
    }

    if (currentStep === "smtp") {
      return (
        <section className="setup-step-card">
          <p className="eyebrow">Step {stepOrder.indexOf("smtp") + 1}</p>
          <h1>SMTP configuration</h1>
          <p className="step-copy">
            Optional. Save email delivery settings now. Pantry can later use this for password
            reset links and other product-facing outbound mail.
          </p>
          <label className="checkbox-row">
            <input
              type="checkbox"
              name="setup_smtp_enabled"
              checked={wizard.smtp_config.is_enabled}
              onChange={(event) =>
                setWizard((current) => ({
                  ...current,
                  skipped_optional_steps: current.skipped_optional_steps.filter(
                    (step) => step !== "smtp"
                  ),
                  smtp_config: {
                    ...current.smtp_config,
                    is_enabled: event.target.checked,
                    password_reset_enabled: event.target.checked
                      ? current.smtp_config.password_reset_enabled
                      : false
                  }
                }))
              }
            />
            <span>Enable SMTP for this installation.</span>
          </label>
          <label className="checkbox-row">
            <input
              type="checkbox"
              name="setup_smtp_password_reset_enabled"
              checked={wizard.smtp_config.password_reset_enabled}
              disabled={!wizard.smtp_config.is_enabled}
              onChange={(event) =>
                setWizard((current) => ({
                  ...current,
                  skipped_optional_steps: current.skipped_optional_steps.filter(
                    (step) => step !== "smtp"
                  ),
                  smtp_config: {
                    ...current.smtp_config,
                    password_reset_enabled: event.target.checked
                  }
                }))
              }
            />
            <span>Allow password reset emails after setup completes.</span>
          </label>
          <p className="helper-text">
            This uses Pantry’s default reset email template. Full template editing stays in the
            admin SMTP settings page.
          </p>
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
                    skipped_optional_steps: current.skipped_optional_steps.filter(
                      (step) => step !== "smtp"
                    ),
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
                    skipped_optional_steps: current.skipped_optional_steps.filter(
                      (step) => step !== "smtp"
                    ),
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
                    skipped_optional_steps: current.skipped_optional_steps.filter(
                      (step) => step !== "smtp"
                    ),
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
                    skipped_optional_steps: current.skipped_optional_steps.filter(
                      (step) => step !== "smtp"
                    ),
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
                    skipped_optional_steps: current.skipped_optional_steps.filter(
                      (step) => step !== "smtp"
                    ),
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
                    skipped_optional_steps: current.skipped_optional_steps.filter(
                      (step) => step !== "smtp"
                    ),
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
        <p className="eyebrow">Step {stepOrder.indexOf("review") + 1}</p>
        <h1>Review and complete</h1>
        <p className="step-copy">
          Check everything looks right, then complete the setup. Pantry will only write staged
          fresh-install data or apply the staged restore bundle once you confirm.
        </p>

        {wizard.installation_mode === "restore_backup" ? (
          <div className="setup-review-layout">
            <div className="stack">
              <ReviewSummaryCard
                title="Install selection"
                badge="Restore"
                onEdit={() => void handleStepJump("welcome")}
              >
                <ReviewSummaryRow
                  label="Backup"
                  value={wizard.staged_restore?.original_filename ?? "No staged restore uploaded yet"}
                  wrap
                />
                <ReviewSummaryRow
                  label="Bundle"
                  value={
                    wizard.staged_restore
                      ? `${wizard.staged_restore.bundle.scope} · Pantry ${wizard.staged_restore.bundle.app_version}`
                      : "Upload a full instance backup bundle."
                  }
                />
                <ReviewSummaryRow
                  label="Status"
                  value={
                    wizard.staged_restore?.supported_for_restore
                      ? "Validated and ready to apply during finalization."
                      : "The staged backup is not ready to restore yet."
                  }
                />
              </ReviewSummaryCard>
            </div>

            <div className="stack">
              <ReviewSummaryCard title="Safety checks">
                {wizard.staged_restore ? (
                  <ul className="callout-list">
                    {wizard.staged_restore.warnings.map((warning) => (
                      <li key={warning}>{warning}</li>
                    ))}
                  </ul>
                ) : (
                  <p>Restore validation warnings will appear here after upload.</p>
                )}
              </ReviewSummaryCard>
            </div>
          </div>
        ) : (
          <div className="setup-review-layout">
            <div className="stack">
              <ReviewSummaryCard
                title="Install selection"
                badge="Fresh install"
                onEdit={() => void handleStepJump("welcome")}
              >
                <ReviewSummaryRow label="Mode" value="Fresh install" />
              </ReviewSummaryCard>

              <ReviewSummaryCard title="Users" onEdit={() => void handleStepJump("users")}>
                <ReviewSummaryRow label="Admin" value={summarizeUser(wizard.admin_user)} />
                <ReviewSummaryRow
                  label="Admin password"
                  value={renderSavedPasswordHint(wizard.admin_user)}
                />
                {wizard.initial_users.length > 0 ? (
                  <div className="review-summary-list">
                    {wizard.initial_users.map((user) => (
                      <p key={user.stage_id}>
                        {summarizeUser(user)} · {renderSavedPasswordHint(user)}
                      </p>
                    ))}
                  </div>
                ) : (
                  <p>No extra users staged yet.</p>
                )}
              </ReviewSummaryCard>

              <ReviewSummaryCard
                title="Household and rooms"
                onEdit={() => void handleStepJump("household")}
              >
                <ReviewSummaryRow label="Household" value={wizard.household_name || "Not configured yet"} />
                <div className="review-summary-list">
                  {wizard.rooms.map((room, index) => (
                    <p key={room.stage_id}>
                      Room {index + 1}: {room.name || "Not configured yet"} ·{" "}
                      {room.storage_locations.length > 0
                        ? room.storage_locations.join(", ")
                        : "No storage locations yet"}
                    </p>
                  ))}
                </div>
                <ReviewSummaryRow
                  label="Members"
                  value={
                    configuredUsers
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
                      .join(", ") || "No household members selected yet"
                  }
                  wrap
                />
              </ReviewSummaryCard>
            </div>

            <div className="stack">
              <ReviewSummaryCard
                title="Dietary preferences"
                badge={wizard.skipped_optional_steps.includes("dietary") ? "Skipped for now" : undefined}
                onEdit={() => void handleStepJump("dietary")}
              >
                <ReviewSummaryRow
                  label="Household"
                  value={
                    wizard.household_dietary_preferences.includes(DIETARY_NONE_OPTION)
                      ? "None selected"
                      : wizard.household_dietary_preferences.length > 0
                        ? wizard.household_dietary_preferences.join(", ")
                        : wizard.skipped_optional_steps.includes("dietary")
                          ? "Skipped for now"
                          : "Not configured"
                  }
                  wrap
                />
                <ReviewSummaryRow
                  label="Personal"
                  value={
                    wizard.user_dietary_preferences.length > 0
                      ? wizard.user_dietary_preferences
                          .map((preference) => {
                            const user = allUsers.find(
                              (candidate) => candidate.stage_id === preference.stage_user_id
                            );
                            const summary = preference.preferences.includes(DIETARY_NONE_OPTION)
                              ? "None selected"
                              : preference.preferences.join(", ");
                            return `${user ? summarizeUser(user) : "Staged user"} (${summary})`;
                          })
                          .join(", ")
                      : wizard.skipped_optional_steps.includes("dietary")
                        ? "Skipped for now"
                        : "Not configured"
                  }
                  wrap
                />
              </ReviewSummaryCard>

              <ReviewSummaryCard
                title="Public URL"
                badge={wizard.skipped_optional_steps.includes("public_url") ? "Skipped for now" : undefined}
                onEdit={() => void handleStepJump("public_url")}
              >
                <ReviewSummaryRow
                  label="Browser URL"
                  value={
                    wizard.public_base_url
                      ? wizard.public_base_url
                      : wizard.skipped_optional_steps.includes("public_url")
                        ? "Skipped for now"
                        : "Not configured"
                  }
                  wrap
                />
              </ReviewSummaryCard>

              <ReviewSummaryCard
                title="AI"
                badge={wizard.skipped_optional_steps.includes("ai") ? "Skipped for now" : undefined}
                onEdit={() => void handleStepJump("ai")}
              >
                <ReviewSummaryRow
                  label="Configuration"
                  value={
                    wizard.ai_config.is_enabled
                      ? `${wizard.ai_config.provider_type} · ${wizard.ai_config.base_url} · ${wizard.ai_config.default_model}`
                      : wizard.skipped_optional_steps.includes("ai")
                        ? "Skipped for now"
                        : "Not configured"
                  }
                  wrap
                />
              </ReviewSummaryCard>

              <ReviewSummaryCard
                title="SMTP"
                badge={wizard.skipped_optional_steps.includes("smtp") ? "Skipped for now" : undefined}
                onEdit={() => void handleStepJump("smtp")}
              >
                <ReviewSummaryRow
                  label="Delivery"
                  value={
                    wizard.smtp_config.is_enabled
                      ? `${wizard.smtp_config.host}:${wizard.smtp_config.port ?? ""}`
                      : wizard.skipped_optional_steps.includes("smtp")
                        ? "Skipped for now"
                        : "Not configured"
                  }
                  wrap
                />
                <ReviewSummaryRow
                  label="Password reset"
                  value={
                    wizard.smtp_config.password_reset_enabled
                      ? "Allowed after setup completes"
                      : wizard.skipped_optional_steps.includes("smtp")
                        ? "Skipped for now"
                        : "Disabled"
                  }
                />
              </ReviewSummaryCard>
            </div>
          </div>
        )}

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
              {wizard.installation_mode === "restore_backup"
                ? "Pantry will restore the staged full instance backup in one final step."
                : "Pantry will create users, the first household, memberships, locations, settings, and any optional integrations in one final step."}
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
        {restoreCannotContinue ? (
          <div className="setup-alert is-error" data-testid="setup-restore-blocked">
            <strong>This backup cannot be restored yet.</strong>
            {restoreValidationIssues.some(
              (issue) => issue.includes("schema revision") || issue.includes("restore-compatible"),
            ) ? <p>Cross-version restore is not supported yet.</p> : null}
            <ul>
              {restoreValidationIssues.map((issue) => (
                <li key={issue}>{issue}</li>
              ))}
            </ul>
          </div>
        ) : null}
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
                disabled={
                  isSaving ||
                  (currentStep === "users" && !usersValidation.canContinue) ||
                  restoreCannotContinue
                }
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

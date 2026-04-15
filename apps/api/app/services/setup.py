from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password, normalize_email
from app.domain.ai import (
    AI_HEALTH_UNKNOWN,
    AI_PROVIDER_API_KEY_REQUIRED,
    AI_PROVIDER_OLLAMA,
    AI_PROVIDER_TYPES,
    AI_SCOPE_INSTANCE,
    AI_SCOPE_KEY_INSTANCE,
    canonical_provider_type,
)
from app.domain.roles import HOUSEHOLD_ADMIN_ROLE, HOUSEHOLD_USER_ROLE, PLATFORM_ADMIN_ROLE
from app.models.ai_provider_config import AIProviderConfig
from app.models.household import Household
from app.models.instance_setting import InstanceSetting
from app.models.location import Location
from app.models.location_group import LocationGroup
from app.models.membership import Membership
from app.models.setup_state import SetupState
from app.models.user import User
from app.schemas.setup import (
    SetupAIConfigUpdateRequest,
    SetupDietaryUpdateRequest,
    SetupHouseholdUpdateRequest,
    SetupModeUpdateRequest,
    SetupPublicURLUpdateRequest,
    SetupSMTPConfigUpdateRequest,
    SetupSMTPTestRequest,
    SetupSMTPTestResponse,
    SetupStatusResponse,
    SetupStagedRestoreSummary,
    SetupStepState,
    SetupUsersUpdateRequest,
    SetupWelcomeUpdateRequest,
    SetupWizardStateResponse,
    StagedSetupAIConfigSummary,
    StagedSetupAssignmentSummary,
    StagedSetupDietaryUserSummary,
    StagedSetupRoomSummary,
    StagedSetupSMTPConfigSummary,
    StagedSetupUserSummary,
)
from app.services.backups import clear_staged_backup, load_staged_backup, restore_instance_backup_bundle, stage_backup_upload
from app.services.ai_config import _normalize_base_url, get_instance_provider_config, normalize_provider_model
from app.services.audit import record_audit_event
from app.services.auth import count_platform_admins, get_user_by_email, get_user_by_external_id
from app.services.instance_settings import (
    _normalize_optional_text,
    _normalize_smtp_port,
    _require_valid_email,
    get_or_create_instance_settings,
    normalize_public_base_url,
    normalize_smtp_host,
    normalize_smtp_security,
)
from app.services.pantry_normalization import dedupe_preserving_order, normalize_lookup_name, require_text
from app.services.roles import get_role_by_code
from app.services.secrets import decrypt_secret, encrypt_secret
from app.services.smtp import test_smtp_connection

SETUP_SCOPE_KEY = "instance"
SETUP_STATUS_IN_PROGRESS = "in_progress"
SETUP_STATUS_COMPLETED = "completed"
DIETARY_NONE_OPTION = "None"
SETUP_STEP_TITLES = {
    "welcome": "Install selection",
    "users": "Admin and users",
    "dietary": "Dietary preferences",
    "household": "Rooms and storage",
    "public_url": "Public URL",
    "ai": "AI configuration",
    "smtp": "SMTP configuration",
    "review": "Review and complete",
}
FRESH_INSTALL_STEP_ORDER = [
    "welcome",
    "users",
    "dietary",
    "household",
    "public_url",
    "ai",
    "smtp",
    "review",
]
RESTORE_STEP_ORDER = ["welcome", "review"]
REQUIRED_STEPS = {"welcome", "users", "household"}
OPTIONAL_STEPS = {"public_url", "dietary", "ai", "smtp"}
DEFAULT_LOCATION_GROUP_NAME = "Kitchen"
DEFAULT_SETUP_ROOM_STAGE_ID = "room-1"
DEFAULT_ADMIN_STAGE_ID = "platform-admin"
SETUP_MODE_FRESH_INSTALL = "fresh_install"
SETUP_MODE_RESTORE_BACKUP = "restore_backup"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _default_room_payload(*, stage_id: str = DEFAULT_SETUP_ROOM_STAGE_ID) -> dict[str, object]:
    return {
        "stage_id": stage_id,
        "name": DEFAULT_LOCATION_GROUP_NAME,
        "storage_locations": [],
    }


def _default_payload() -> dict[str, object]:
    return {
        "welcome_acknowledged": False,
        "installation_mode": SETUP_MODE_FRESH_INSTALL,
        "staged_restore": None,
        "admin_user": {
            "stage_id": DEFAULT_ADMIN_STAGE_ID,
            "login": "",
            "display_name": "",
            "password_hash": None,
        },
        "initial_users": [],
        "household": {
            "name": "",
            "rooms": [_default_room_payload()],
            "assignments": [],
        },
        "public_base_url": "",
        "skipped_optional_steps": [],
        "dietary": {
            "household_preferences": [],
            "user_preferences": {},
        },
        "ai": {
            "provider_type": None,
            "base_url": "",
            "default_model": "",
            "is_enabled": False,
        },
        "smtp": {
            "host": "",
            "port": None,
            "username": "",
            "from_email": "",
            "from_name": "",
            "security": None,
            "is_enabled": False,
            "password_reset_enabled": False,
        },
    }


def _normalize_setup_rooms(raw_rooms: list[dict[str, object]] | None) -> list[dict[str, object]]:
    if not raw_rooms:
        return [_default_room_payload()]

    normalized_rooms: list[dict[str, object]] = []
    seen_room_names: set[str] = set()
    for index, room in enumerate(raw_rooms):
        stage_id = str(room.get("stage_id") or f"room-{index + 1}")
        room_name = _normalize_optional_text(room.get("name") if isinstance(room.get("name"), str) else None)
        normalized_room_name = normalize_lookup_name(room_name) if room_name else None
        if normalized_room_name:
            if normalized_room_name in seen_room_names:
                raise ValueError("Each staged room must have a unique name.")
            seen_room_names.add(normalized_room_name)

        storage_locations = dedupe_preserving_order(
            [str(item).strip() for item in room.get("storage_locations") or [] if str(item).strip()]
        )
        normalized_rooms.append(
            {
                "stage_id": stage_id,
                "name": room_name,
                "storage_locations": storage_locations,
            }
        )

    return normalized_rooms or [_default_room_payload()]


def _get_setup_state_record(db: Session) -> SetupState | None:
    return db.scalar(select(SetupState).where(SetupState.scope_key == SETUP_SCOPE_KEY))


def _get_or_create_setup_state(db: Session) -> SetupState:
    state = _get_setup_state_record(db)
    if state is None:
        state = SetupState(scope_key=SETUP_SCOPE_KEY, status=SETUP_STATUS_IN_PROGRESS, payload=_default_payload())
        db.add(state)
        db.flush()
    return state


def _merged_payload(payload: dict[str, object] | None) -> dict[str, object]:
    merged = deepcopy(_default_payload())
    source = payload or {}

    if "welcome_acknowledged" in source:
        merged["welcome_acknowledged"] = bool(source.get("welcome_acknowledged"))
    if source.get("installation_mode") in {SETUP_MODE_FRESH_INSTALL, SETUP_MODE_RESTORE_BACKUP}:
        merged["installation_mode"] = source.get("installation_mode")
    if isinstance(source.get("staged_restore"), dict):
        merged["staged_restore"] = source.get("staged_restore")

    if isinstance(source.get("admin_user"), dict):
        merged["admin_user"].update(source["admin_user"])  # type: ignore[arg-type]
    if isinstance(source.get("initial_users"), list):
        merged["initial_users"] = source["initial_users"]
    if isinstance(source.get("household"), dict):
        household = source["household"]
        merged["household"]["name"] = household.get("name") or ""
        merged["household"]["assignments"] = household.get("assignments") or []
        raw_rooms = household.get("rooms") if isinstance(household.get("rooms"), list) else None
        if raw_rooms is None:
            raw_rooms = [
                {
                    "stage_id": DEFAULT_SETUP_ROOM_STAGE_ID,
                    "name": household.get("location_group_name"),
                    "storage_locations": household.get("storage_locations") or [],
                }
            ]
        merged["household"]["rooms"] = _normalize_setup_rooms(raw_rooms)  # type: ignore[arg-type]
    if isinstance(source.get("public_base_url"), str):
        merged["public_base_url"] = source["public_base_url"]
    if isinstance(source.get("skipped_optional_steps"), list):
        merged["skipped_optional_steps"] = [
            str(step)
            for step in source["skipped_optional_steps"]
            if str(step) in OPTIONAL_STEPS
        ]
    if isinstance(source.get("dietary"), dict):
        merged["dietary"].update(source["dietary"])  # type: ignore[arg-type]
    if isinstance(source.get("ai"), dict):
        merged["ai"].update(source["ai"])  # type: ignore[arg-type]
    if isinstance(source.get("smtp"), dict):
        merged["smtp"].update(source["smtp"])  # type: ignore[arg-type]

    household = merged["household"]
    household["rooms"] = _normalize_setup_rooms(household.get("rooms") if isinstance(household.get("rooms"), list) else None)

    return merged


def _normalize_login(value: str) -> str:
    return normalize_email(value)


def _normalize_optional_display_name(value: str | None) -> str | None:
    normalized = _normalize_optional_text(value)
    return normalized


def _normalize_password_hash(password: str | None, *, existing_hash: str | None) -> str | None:
    if password is None:
        return existing_hash
    if not password.strip():
        return existing_hash
    if len(password) < 8:
        raise ValueError("Passwords must be at least 8 characters.")
    return hash_password(password)


def _normalize_preferences(values: list[str]) -> list[str]:
    return dedupe_preserving_order([item.strip() for item in values if item.strip()])


def _normalize_setup_dietary_preferences(values: list[str]) -> list[str]:
    normalized = _normalize_preferences(values)
    if any(value.casefold() == DIETARY_NONE_OPTION.casefold() for value in normalized):
        return [DIETARY_NONE_OPTION]
    return normalized


def _normalize_final_dietary_preferences(values: list[str]) -> list[str]:
    return [
        value
        for value in _normalize_setup_dietary_preferences(values)
        if value.casefold() != DIETARY_NONE_OPTION.casefold()
    ]


def _normalize_optional_public_base_url(value: str | None) -> str | None:
    normalized = _normalize_optional_text(value)
    if normalized is None:
        return None
    return normalize_public_base_url(normalized)


def _serialize_user(user: dict[str, object], *, is_platform_admin: bool) -> StagedSetupUserSummary:
    return StagedSetupUserSummary(
        stage_id=str(user.get("stage_id") or DEFAULT_ADMIN_STAGE_ID),
        login=str(user.get("login") or ""),
        display_name=_normalize_optional_display_name(user.get("display_name") if isinstance(user.get("display_name"), str) else None),
        password_saved=bool(user.get("password_hash")),
        is_platform_admin=is_platform_admin,
    )


def _serialize_room(room: dict[str, object]) -> StagedSetupRoomSummary:
    return StagedSetupRoomSummary(
        stage_id=str(room.get("stage_id") or DEFAULT_SETUP_ROOM_STAGE_ID),
        name=_normalize_optional_text(room.get("name") if isinstance(room.get("name"), str) else None),
        storage_locations=[str(item) for item in room.get("storage_locations") or []],
    )


def _current_step_keys(payload: dict[str, object]) -> list[str]:
    if payload.get("installation_mode") == SETUP_MODE_RESTORE_BACKUP:
        return RESTORE_STEP_ORDER
    return FRESH_INSTALL_STEP_ORDER


def _serialize_staged_restore(payload: dict[str, object]) -> SetupStagedRestoreSummary | None:
    staged_restore = payload.get("staged_restore")
    if not isinstance(staged_restore, dict):
        return None
    bundle = staged_restore.get("bundle")
    if not isinstance(bundle, dict):
        return None

    return SetupStagedRestoreSummary.model_validate(
        {
            "stage_id": staged_restore.get("stage_id"),
            "original_filename": staged_restore.get("original_filename"),
            "size_bytes": staged_restore.get("size_bytes"),
            "uploaded_at": staged_restore.get("uploaded_at"),
            "quarantine_path": staged_restore.get("quarantine_path"),
            "supported_for_restore": staged_restore.get("supported_for_restore"),
            "warnings": staged_restore.get("warnings") or [],
            "bundle": bundle,
        }
    )


def _serialize_steps(payload: dict[str, object]) -> list[SetupStepState]:
    steps = _compute_step_completion(payload)
    return [
        SetupStepState(
            key=key,
            title=SETUP_STEP_TITLES[key],
            required=key in REQUIRED_STEPS or key == "review",
            is_complete=is_complete,
        )
        for key in _current_step_keys(payload)
        for is_complete in [steps[key]]
    ]


def _compute_step_completion(payload: dict[str, object]) -> dict[str, bool]:
    installation_mode = payload.get("installation_mode")
    admin_user = payload["admin_user"]
    initial_users = payload["initial_users"]
    household = payload["household"]
    dietary = payload["dietary"]
    ai = payload["ai"]
    smtp = payload["smtp"]
    staged_restore = payload.get("staged_restore") if isinstance(payload.get("staged_restore"), dict) else None
    skipped_optional_steps = set(payload.get("skipped_optional_steps") or [])
    rooms = _normalize_setup_rooms(household.get("rooms") if isinstance(household.get("rooms"), list) else None)
    install_selection_complete = bool(
        installation_mode == SETUP_MODE_FRESH_INSTALL
        or (staged_restore and staged_restore.get("supported_for_restore"))
    )
    welcome_complete = bool(payload.get("welcome_acknowledged")) and bool(install_selection_complete)

    users_complete = (
        bool(admin_user.get("login"))
        and bool(admin_user.get("password_hash"))
        and all(bool(user.get("login")) and bool(user.get("password_hash")) for user in initial_users)
    )
    household_complete = bool(str(household.get("name") or "").strip()) and bool(rooms) and all(
        bool(str(room.get("name") or "").strip()) and len(room.get("storage_locations") or []) > 0
        for room in rooms
    )
    public_url_complete = bool(str(payload.get("public_base_url") or "").strip()) or "public_url" in skipped_optional_steps
    dietary_complete = (
        bool(dietary.get("household_preferences") or dietary.get("user_preferences"))
        or "dietary" in skipped_optional_steps
    )
    ai_enabled = bool(ai.get("is_enabled"))
    ai_complete = (
        ai_enabled
        and bool(ai.get("provider_type"))
        and bool(ai.get("base_url"))
        and bool(ai.get("default_model"))
    ) or "ai" in skipped_optional_steps
    smtp_enabled = bool(smtp.get("is_enabled"))
    smtp_complete = (smtp_enabled and bool(smtp.get("host"))) or "smtp" in skipped_optional_steps
    if installation_mode == SETUP_MODE_RESTORE_BACKUP:
        users_complete = True
        household_complete = True
        public_url_complete = True
        dietary_complete = True
        ai_complete = True
        smtp_complete = True

    review_complete = all(
        [welcome_complete, users_complete, household_complete]
    )

    return {
        "welcome": welcome_complete,
        "users": users_complete,
        "dietary": dietary_complete,
        "household": household_complete,
        "public_url": public_url_complete,
        "ai": ai_complete,
        "smtp": smtp_complete,
        "review": review_complete,
    }


def _missing_requirements(payload: dict[str, object]) -> list[str]:
    missing: list[str] = []
    completion = _compute_step_completion(payload)
    if not completion["welcome"]:
        if payload.get("installation_mode") == SETUP_MODE_RESTORE_BACKUP:
            missing.append("Choose restore and upload a validated full instance Pantry backup.")
        else:
            missing.append("Choose how this Pantry install should start before continuing.")
    if payload.get("installation_mode") == SETUP_MODE_RESTORE_BACKUP:
        return missing
    if not completion["users"]:
        missing.append("Create a platform admin login and save a password.")
    if not completion["household"]:
        missing.append("Add the first household and at least one room with storage locations.")
    return missing


def is_setup_complete(db: Session) -> bool:
    state = _get_setup_state_record(db)
    if state and state.status == SETUP_STATUS_COMPLETED:
        return True
    return state is None and db.scalar(select(User.id).limit(1)) is not None


def mark_setup_completed(db: Session) -> SetupState:
    state = _get_or_create_setup_state(db)
    state.status = SETUP_STATUS_COMPLETED
    state.payload = {}
    state.encrypted_ai_api_key = None
    state.encrypted_smtp_password = None
    state.completed_at = _utc_now()
    db.add(state)
    db.commit()
    db.refresh(state)
    return state


def get_setup_status(db: Session) -> SetupStatusResponse:
    state = _get_setup_state_record(db)
    payload = _merged_payload(state.payload if state else None)
    platform_admin_count = count_platform_admins(db)
    is_initialized = bool(state and state.status == SETUP_STATUS_COMPLETED) or (
        state is None and db.scalar(select(User.id).limit(1)) is not None
    )
    has_staged_progress = bool(
        state
        and state.status != SETUP_STATUS_COMPLETED
        and any(
            [
                payload.get("welcome_acknowledged"),
                payload.get("installation_mode") == SETUP_MODE_RESTORE_BACKUP,
                payload.get("staged_restore"),
                payload["admin_user"].get("login"),
                payload["initial_users"],
                payload["household"].get("name"),
                any(
                    room.get("name") or room.get("storage_locations")
                    for room in payload["household"].get("rooms") or []
                ),
                payload.get("public_base_url"),
            ]
        )
    )
    return SetupStatusResponse(
        is_initialized=is_initialized,
        platform_admin_count=platform_admin_count,
        can_bootstrap_platform_admin=not is_initialized,
        recommended_next_step=(
            "Sign in and continue in Pantry."
            if is_initialized
            else "Resume setup."
            if has_staged_progress
            else "Run the first-run setup wizard."
        ),
        stage="completed" if is_initialized else "in_progress" if has_staged_progress else "not_started",
        has_staged_progress=has_staged_progress,
        completed_at=state.completed_at if state else None,
        steps=(
            [
                SetupStepState(key=key, title=title, required=key in REQUIRED_STEPS or key == "review", is_complete=True)
                for key, title in SETUP_STEP_TITLES.items()
            ]
            if is_initialized
            else _serialize_steps(payload)
        ),
    )


def get_setup_wizard_state(db: Session) -> SetupWizardStateResponse:
    state = _get_or_create_setup_state(db)
    payload = _merged_payload(state.payload)
    admin_user = payload["admin_user"]
    initial_users = payload["initial_users"]
    household = payload["household"]
    dietary = payload["dietary"]
    ai = payload["ai"]
    smtp = payload["smtp"]
    rooms = _normalize_setup_rooms(household.get("rooms") if isinstance(household.get("rooms"), list) else None)
    first_room = rooms[0] if rooms else _default_room_payload()

    return SetupWizardStateResponse(
        status=get_setup_status(db),
        installation_mode=payload.get("installation_mode") or SETUP_MODE_FRESH_INSTALL,
        welcome_acknowledged=bool(payload.get("welcome_acknowledged")),
        staged_restore=_serialize_staged_restore(payload),
        admin_user=_serialize_user(admin_user, is_platform_admin=True),
        initial_users=[_serialize_user(user, is_platform_admin=False) for user in initial_users],
        household_name=_normalize_optional_text(str(household.get("name") or "")),
        rooms=[_serialize_room(room) for room in rooms],
        location_group_name=_normalize_optional_text(str(first_room.get("name") or DEFAULT_LOCATION_GROUP_NAME)),
        storage_locations=[str(item) for item in first_room.get("storage_locations") or []],
        household_assignments=[
            StagedSetupAssignmentSummary(
                stage_user_id=str(item.get("stage_user_id") or ""),
                role=str(item.get("role") or HOUSEHOLD_USER_ROLE),
            )
            for item in household.get("assignments") or []
            if item.get("stage_user_id")
        ],
        public_base_url=_normalize_optional_text(str(payload.get("public_base_url") or "")),
        skipped_optional_steps=[
            str(step)
            for step in payload.get("skipped_optional_steps") or []
            if str(step) in OPTIONAL_STEPS
        ],
        household_dietary_preferences=[str(item) for item in dietary.get("household_preferences") or []],
        user_dietary_preferences=[
            StagedSetupDietaryUserSummary(stage_user_id=stage_user_id, preferences=[str(item) for item in preferences])
            for stage_user_id, preferences in (dietary.get("user_preferences") or {}).items()
        ],
        ai_config=StagedSetupAIConfigSummary(
            provider_type=canonical_provider_type(ai.get("provider_type")),
            base_url=_normalize_optional_text(str(ai.get("base_url") or "")),
            default_model=_normalize_optional_text(str(ai.get("default_model") or "")),
            is_enabled=bool(ai.get("is_enabled")),
            has_api_key=bool(state.encrypted_ai_api_key),
        ),
        smtp_config=StagedSetupSMTPConfigSummary(
            host=_normalize_optional_text(str(smtp.get("host") or "")),
            port=smtp.get("port"),
            username=_normalize_optional_text(str(smtp.get("username") or "")),
            has_password=bool(state.encrypted_smtp_password),
            from_email=_normalize_optional_text(str(smtp.get("from_email") or "")),
            from_name=_normalize_optional_text(str(smtp.get("from_name") or "")),
            security=smtp.get("security"),
            is_enabled=bool(smtp.get("is_enabled")),
            password_reset_enabled=bool(smtp.get("password_reset_enabled")),
        ),
        can_complete=len(_missing_requirements(payload)) == 0,
        missing_requirements=_missing_requirements(payload),
    )


def update_setup_welcome(db: Session, payload: SetupWelcomeUpdateRequest) -> SetupWizardStateResponse:
    state = _get_or_create_setup_state(db)
    merged = _merged_payload(state.payload)
    merged["welcome_acknowledged"] = payload.acknowledged
    state.payload = merged
    db.add(state)
    db.commit()
    return get_setup_wizard_state(db)


def update_setup_mode(db: Session, payload: SetupModeUpdateRequest) -> SetupWizardStateResponse:
    state = _get_or_create_setup_state(db)
    merged = _merged_payload(state.payload)
    previous_stage_id = None
    if isinstance(merged.get("staged_restore"), dict):
        previous_stage_id = merged["staged_restore"].get("stage_id")

    merged["installation_mode"] = payload.installation_mode
    if payload.installation_mode == SETUP_MODE_FRESH_INSTALL:
        merged["staged_restore"] = None
        if previous_stage_id:
            clear_staged_backup(get_settings(), stage_id=str(previous_stage_id))

    state.payload = merged
    db.add(state)
    db.commit()
    return get_setup_wizard_state(db)


async def stage_setup_restore_upload(db: Session, upload) -> SetupWizardStateResponse:
    state = _get_or_create_setup_state(db)
    merged = _merged_payload(state.payload)
    previous_stage_id = None
    if isinstance(merged.get("staged_restore"), dict):
        previous_stage_id = merged["staged_restore"].get("stage_id")

    staged = await stage_backup_upload(
        db,
        settings=get_settings(),
        upload=upload,
        allowed_restore_scopes={"instance"},
    )

    merged["installation_mode"] = SETUP_MODE_RESTORE_BACKUP
    merged["staged_restore"] = {
        "stage_id": staged.stage_id,
        "original_filename": staged.original_filename,
        "size_bytes": staged.size_bytes,
        "uploaded_at": staged.uploaded_at.isoformat(),
        "quarantine_path": staged.quarantine_path,
        "supported_for_restore": staged.supported_for_restore,
        "warnings": list(staged.warnings),
        "bundle": {
            **staged.bundle,
            "exported_at": staged.bundle["exported_at"],
        },
    }
    state.payload = merged
    db.add(state)
    db.commit()

    if previous_stage_id:
        clear_staged_backup(get_settings(), stage_id=str(previous_stage_id))

    return get_setup_wizard_state(db)


def update_setup_users(db: Session, payload: SetupUsersUpdateRequest) -> SetupWizardStateResponse:
    state = _get_or_create_setup_state(db)
    merged = _merged_payload(state.payload)
    existing_admin = merged["admin_user"]

    admin_login = _normalize_login(payload.admin_login)
    staged_logins = {admin_login} if admin_login else set()
    merged["admin_user"] = {
        "stage_id": DEFAULT_ADMIN_STAGE_ID,
        "login": admin_login,
        "display_name": _normalize_optional_display_name(payload.admin_display_name),
        "password_hash": _normalize_password_hash(
            payload.admin_password,
            existing_hash=existing_admin.get("password_hash"),
        ),
    }

    initial_users: list[dict[str, object]] = []
    for user in payload.initial_users:
        login = _normalize_login(user.login)
        if login and login in staged_logins:
            raise ValueError("Each staged user must have a unique username.")
        if login:
            staged_logins.add(login)

        existing_user = next(
            (
                candidate
                for candidate in merged["initial_users"]
                if str(candidate.get("stage_id")) == user.stage_id
            ),
            None,
        )
        initial_users.append(
            {
                "stage_id": user.stage_id,
                "login": login,
                "display_name": _normalize_optional_display_name(user.display_name),
                "password_hash": _normalize_password_hash(
                    user.password,
                    existing_hash=existing_user.get("password_hash") if existing_user else None,
                ),
            }
        )

    merged["initial_users"] = initial_users
    state.payload = merged
    db.add(state)
    db.commit()
    return get_setup_wizard_state(db)


def update_setup_household(db: Session, payload: SetupHouseholdUpdateRequest) -> SetupWizardStateResponse:
    state = _get_or_create_setup_state(db)
    merged = _merged_payload(state.payload)
    raw_rooms = (
        [
            {
                "stage_id": room.stage_id,
                "name": room.name,
                "storage_locations": room.storage_locations,
            }
            for room in payload.rooms
        ]
        if payload.rooms
        else [
            {
                "stage_id": DEFAULT_SETUP_ROOM_STAGE_ID,
                "name": payload.location_group_name,
                "storage_locations": payload.storage_locations,
            }
        ]
    )

    merged["household"] = {
        "name": payload.household_name.strip(),
        "rooms": _normalize_setup_rooms(raw_rooms),
        "assignments": [
            {"stage_user_id": assignment.stage_user_id, "role": assignment.role}
            for assignment in payload.household_assignments
        ],
    }
    state.payload = merged
    db.add(state)
    db.commit()
    return get_setup_wizard_state(db)


def update_setup_public_url(db: Session, payload: SetupPublicURLUpdateRequest) -> SetupWizardStateResponse:
    state = _get_or_create_setup_state(db)
    merged = _merged_payload(state.payload)
    merged["public_base_url"] = _normalize_optional_public_base_url(payload.public_base_url) or ""
    skipped_steps = set(merged.get("skipped_optional_steps") or [])
    if merged["public_base_url"]:
        skipped_steps.discard("public_url")
    elif payload.mark_skipped:
        skipped_steps.add("public_url")
    merged["skipped_optional_steps"] = sorted(skipped_steps)
    state.payload = merged
    db.add(state)
    db.commit()
    return get_setup_wizard_state(db)


def update_setup_dietary(db: Session, payload: SetupDietaryUpdateRequest) -> SetupWizardStateResponse:
    state = _get_or_create_setup_state(db)
    merged = _merged_payload(state.payload)
    merged["dietary"] = {
        "household_preferences": _normalize_setup_dietary_preferences(payload.household_preferences),
        "user_preferences": {
            item.stage_user_id: _normalize_setup_dietary_preferences(item.preferences)
            for item in payload.user_preferences
            if _normalize_setup_dietary_preferences(item.preferences)
        },
    }
    skipped_steps = set(merged.get("skipped_optional_steps") or [])
    if merged["dietary"]["household_preferences"] or merged["dietary"]["user_preferences"]:
        skipped_steps.discard("dietary")
    elif payload.mark_skipped:
        skipped_steps.add("dietary")
    merged["skipped_optional_steps"] = sorted(skipped_steps)
    state.payload = merged
    db.add(state)
    db.commit()
    return get_setup_wizard_state(db)


def update_setup_ai(db: Session, payload: SetupAIConfigUpdateRequest) -> SetupWizardStateResponse:
    state = _get_or_create_setup_state(db)
    merged = _merged_payload(state.payload)
    provider_type = canonical_provider_type(payload.provider_type)

    if not payload.is_enabled and not any([provider_type, payload.base_url, payload.default_model, payload.api_key]):
        merged["ai"] = {"provider_type": None, "base_url": "", "default_model": "", "is_enabled": False}
        state.encrypted_ai_api_key = None
    else:
        if provider_type not in AI_PROVIDER_TYPES:
            raise ValueError("Unsupported AI provider type.")
        if not payload.base_url:
            raise ValueError("Provider base URL is required.")
        if not payload.default_model or not payload.default_model.strip():
            raise ValueError("Default model is required.")

        api_key = _normalize_optional_text(payload.api_key)
        if AI_PROVIDER_API_KEY_REQUIRED[provider_type] and not (api_key or state.encrypted_ai_api_key):
            raise ValueError(f"An API key is required for {provider_type} providers.")

        merged["ai"] = {
            "provider_type": provider_type,
            "base_url": _normalize_base_url(payload.base_url),
            "default_model": normalize_provider_model(provider_type, payload.default_model),
            "is_enabled": payload.is_enabled,
        }
        if api_key:
            state.encrypted_ai_api_key = encrypt_secret(api_key)

    skipped_steps = set(merged.get("skipped_optional_steps") or [])
    if (
        merged["ai"].get("is_enabled")
        and merged["ai"].get("provider_type")
        and merged["ai"].get("base_url")
        and merged["ai"].get("default_model")
    ):
        skipped_steps.discard("ai")
    elif payload.mark_skipped:
        skipped_steps.add("ai")
    merged["skipped_optional_steps"] = sorted(skipped_steps)

    state.payload = merged
    db.add(state)
    db.commit()
    return get_setup_wizard_state(db)


def update_setup_smtp(db: Session, payload: SetupSMTPConfigUpdateRequest) -> SetupWizardStateResponse:
    state = _get_or_create_setup_state(db)
    merged = _merged_payload(state.payload)

    has_any_values = any(
        [
            payload.host,
            payload.port is not None,
            payload.username,
            payload.password,
            payload.from_email,
            payload.from_name,
            payload.security,
            payload.is_enabled,
        ]
    )
    if not has_any_values:
        merged["smtp"] = {
            "host": "",
            "port": None,
            "username": "",
            "from_email": "",
            "from_name": "",
            "security": None,
            "is_enabled": False,
            "password_reset_enabled": False,
        }
        state.encrypted_smtp_password = None
    else:
        host = normalize_smtp_host(payload.host)
        if not host:
            raise ValueError("SMTP host is required when saving SMTP configuration.")

        security = normalize_smtp_security(payload.security)
        username = _normalize_optional_text(payload.username)
        password = _normalize_optional_text(payload.password)
        if username and not (password or state.encrypted_smtp_password):
            raise ValueError("An SMTP password is required when an SMTP username is configured.")
        if password and not username:
            raise ValueError("An SMTP username is required when an SMTP password is configured.")

        merged["smtp"] = {
            "host": host,
            "port": _normalize_smtp_port(payload.port, security=security),
            "username": username,
            "from_email": _require_valid_email(payload.from_email, field_name="SMTP from email")
            if _normalize_optional_text(payload.from_email)
            else None,
            "from_name": _normalize_optional_text(payload.from_name),
            "security": security,
            "is_enabled": payload.is_enabled,
            "password_reset_enabled": payload.password_reset_enabled and payload.is_enabled,
        }
        if password:
            state.encrypted_smtp_password = encrypt_secret(password)

    skipped_steps = set(merged.get("skipped_optional_steps") or [])
    if merged["smtp"].get("host"):
        skipped_steps.discard("smtp")
    elif payload.mark_skipped:
        skipped_steps.add("smtp")
    merged["skipped_optional_steps"] = sorted(skipped_steps)

    state.payload = merged
    db.add(state)
    db.commit()
    return get_setup_wizard_state(db)


def test_setup_smtp(db: Session, payload: SetupSMTPTestRequest) -> SetupSMTPTestResponse:
    state = _get_or_create_setup_state(db)
    host = normalize_smtp_host(payload.host)
    if not host:
        raise ValueError("SMTP host is required when testing SMTP configuration.")

    security = normalize_smtp_security(payload.security)
    port = _normalize_smtp_port(payload.port, security=security)
    username = _normalize_optional_text(payload.username)
    password = _normalize_optional_text(payload.password)
    if username and not (password or state.encrypted_smtp_password):
        raise ValueError("An SMTP password is required when an SMTP username is configured.")
    if password and not username:
        raise ValueError("An SMTP username is required when an SMTP password is configured.")

    result = test_smtp_connection(
        host=host,
        port=port,
        username=username,
        password=password or (decrypt_secret(state.encrypted_smtp_password) if state.encrypted_smtp_password else None),
        security=security,
    )
    return SetupSMTPTestResponse(
        ok=result.ok,
        status=result.status,
        message=result.message,
    )


def _role_or_error(db: Session, code: str):
    role = get_role_by_code(db, code)
    if role is None:
        raise ValueError(f"Required role {code} is missing.")
    return role


def _get_first_platform_admin_user(db: Session) -> User | None:
    platform_admin_role = get_role_by_code(db, PLATFORM_ADMIN_ROLE)
    if platform_admin_role is None:
        return None
    return db.scalar(select(User).where(User.platform_role_id == platform_admin_role.id).order_by(User.email))


def finalize_setup(db: Session) -> User:
    if is_setup_complete(db):
        raise ValueError("Initial setup has already been completed.")

    state = _get_or_create_setup_state(db)
    payload = _merged_payload(state.payload)
    missing = _missing_requirements(payload)
    if missing:
        raise ValueError("Setup is incomplete. " + " ".join(missing))

    if payload.get("installation_mode") == SETUP_MODE_RESTORE_BACKUP:
        staged_restore = payload.get("staged_restore")
        if not isinstance(staged_restore, dict) or not staged_restore.get("stage_id"):
            raise ValueError("A staged restore backup is required before finishing setup.")

        bundle = load_staged_backup(get_settings(), stage_id=str(staged_restore["stage_id"]))
        restore_instance_backup_bundle(db, bundle=bundle, actor_external_id=None)
        clear_staged_backup(get_settings(), stage_id=str(staged_restore["stage_id"]))

        admin_user = _get_first_platform_admin_user(db)
        if admin_user is None:
            raise ValueError("The restored backup did not include a platform admin account.")
        return get_user_by_external_id(db, admin_user.external_id) or admin_user

    platform_admin_role = _role_or_error(db, PLATFORM_ADMIN_ROLE)
    household_admin_role = _role_or_error(db, HOUSEHOLD_ADMIN_ROLE)
    household_user_role = _role_or_error(db, HOUSEHOLD_USER_ROLE)

    admin_payload = payload["admin_user"]
    staged_users = [admin_payload, *payload["initial_users"]]
    created_users: dict[str, User] = {}
    dietary = payload["dietary"]
    user_preferences = dietary.get("user_preferences") or {}

    try:
        for staged_user in staged_users:
            login = _normalize_login(str(staged_user.get("login") or ""))
            if not login:
                raise ValueError("Each staged user needs a username.")
            if get_user_by_email(db, login) is not None:
                raise ValueError(f"The username {login} is already in use.")
            password_hash = staged_user.get("password_hash")
            if not password_hash:
                raise ValueError(f"The user {login} does not have a saved password yet.")

            user = User(
                email=login,
                password_hash=str(password_hash),
                display_name=_normalize_optional_display_name(staged_user.get("display_name") if isinstance(staged_user.get("display_name"), str) else None),
                platform_role_id=platform_admin_role.id if str(staged_user.get("stage_id")) == DEFAULT_ADMIN_STAGE_ID else None,
                dietary_preferences=_normalize_final_dietary_preferences(
                    user_preferences.get(str(staged_user.get("stage_id")), [])
                )
                or None,
            )
            db.add(user)
            db.flush()
            created_users[str(staged_user.get("stage_id"))] = user

        household_data = payload["household"]
        household = Household(
            name=require_text(str(household_data.get("name") or ""), field_name="Household name"),
            dietary_preferences=_normalize_final_dietary_preferences(
                dietary.get("household_preferences", [])
            )
            or None,
        )
        db.add(household)
        db.flush()

        rooms = _normalize_setup_rooms(household_data.get("rooms") if isinstance(household_data.get("rooms"), list) else None)
        total_storage_location_count = 0
        for room in rooms:
            room_name = require_text(str(room.get("name") or ""), field_name="Room name")
            location_group = LocationGroup(
                household_id=household.id,
                name=room_name,
                normalized_name=normalize_lookup_name(room_name),
            )
            db.add(location_group)
            db.flush()

            for location_name in room.get("storage_locations") or []:
                display_name = require_text(str(location_name), field_name="Storage location")
                db.add(
                    Location(
                        household_id=household.id,
                        location_group_id=location_group.id,
                        name=display_name,
                        normalized_name=normalize_lookup_name(display_name),
                    )
                )
                total_storage_location_count += 1

        assignments = {item["stage_user_id"]: item["role"] for item in household_data.get("assignments") or []}
        assignments[DEFAULT_ADMIN_STAGE_ID] = HOUSEHOLD_ADMIN_ROLE
        for stage_user_id, user in created_users.items():
            role_code = assignments.get(stage_user_id)
            if not role_code:
                continue
            role = household_admin_role if role_code == HOUSEHOLD_ADMIN_ROLE else household_user_role
            db.add(Membership(user_id=user.id, household_id=household.id, role_id=role.id, is_active=True))

        settings = get_or_create_instance_settings(db)
        settings.public_base_url = _normalize_optional_public_base_url(
            payload.get("public_base_url") if isinstance(payload.get("public_base_url"), str) else None
        )

        smtp_payload = payload["smtp"]
        smtp_host = _normalize_optional_text(smtp_payload.get("host") if isinstance(smtp_payload.get("host"), str) else None)
        if smtp_host:
            settings.smtp_host = smtp_host
            settings.smtp_port = _normalize_smtp_port(smtp_payload.get("port"), security=str(smtp_payload.get("security") or "starttls"))
            settings.smtp_username = _normalize_optional_text(smtp_payload.get("username") if isinstance(smtp_payload.get("username"), str) else None)
            settings.encrypted_smtp_password = state.encrypted_smtp_password
            settings.smtp_from_email = smtp_payload.get("from_email")
            settings.smtp_from_name = smtp_payload.get("from_name")
            settings.smtp_security = smtp_payload.get("security")
            settings.smtp_enabled = bool(smtp_payload.get("is_enabled"))
            settings.password_reset_enabled = bool(smtp_payload.get("password_reset_enabled"))
            settings.smtp_last_test_status = "never"
            settings.smtp_last_tested_at = None
            settings.smtp_last_test_error = None

        ai_payload = payload["ai"]
        if ai_payload.get("is_enabled") and ai_payload.get("provider_type") and ai_payload.get("base_url") and ai_payload.get("default_model"):
            provider_type = canonical_provider_type(str(ai_payload["provider_type"]))
            if provider_type is None:
                raise ValueError("Unsupported AI provider type.")
            config = get_instance_provider_config(db)
            if config is None:
                config = AIProviderConfig(
                    scope_type=AI_SCOPE_INSTANCE,
                    scope_key=AI_SCOPE_KEY_INSTANCE,
                    provider_type=provider_type,
                    base_url=str(ai_payload["base_url"]),
                    default_model=normalize_provider_model(provider_type, str(ai_payload["default_model"])),
                    is_enabled=True,
                )
                db.add(config)
            config.provider_type = provider_type
            config.base_url = str(ai_payload["base_url"])
            config.default_model = normalize_provider_model(provider_type, str(ai_payload["default_model"]))
            config.encrypted_api_key = state.encrypted_ai_api_key
            config.is_enabled = True
            config.health_status = AI_HEALTH_UNKNOWN
            config.health_checked_at = None
            config.health_error = None
            config.available_model_count = 0
            config.capabilities = {}
            config.last_success_at = None

        admin_user = created_users[DEFAULT_ADMIN_STAGE_ID]
        record_audit_event(
            db,
            household=household,
            actor=admin_user,
            action="setup.completed",
            target_type="setup_state",
            target_external_id=state.external_id,
            event_metadata={
                "household_external_id": household.external_id,
                "room_count": len(rooms),
                "storage_location_count": total_storage_location_count,
                "initial_user_count": len(payload["initial_users"]),
                "public_base_url": settings.public_base_url,
                "ai_enabled": bool(ai_payload.get("is_enabled")),
                "smtp_enabled": bool(smtp_payload.get("is_enabled")),
            },
        )

        state.status = SETUP_STATUS_COMPLETED
        state.payload = {}
        state.encrypted_ai_api_key = None
        state.encrypted_smtp_password = None
        state.completed_at = _utc_now()
        db.add(state)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return get_user_by_external_id(db, created_users[DEFAULT_ADMIN_STAGE_ID].external_id) or created_users[DEFAULT_ADMIN_STAGE_ID]

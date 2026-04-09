from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.api.deps.auth import require_platform_admin
from app.core.config import get_settings
from app.core.db import get_db_session
from app.models.household import Household
from app.models.membership import Membership
from app.models.role import Role
from app.models.user import User
from app.schemas.admin import (
    AdminActionResponse,
    AdminHouseholdMemberSummary,
    AdminHouseholdSummary,
    AdminOverviewResponse,
    AdminUserMembershipSummary,
    AdminUserSummary,
    CreateAdminHouseholdRequest,
    CreateAdminMembershipRequest,
    CreateAdminUserRequest,
    DeleteAdminHouseholdRequest,
    UpdateAdminUserRequest,
    UpdateAdminHouseholdRequest,
)
from app.schemas.backups import (
    BackupBundleSummary,
    HouseholdBackupRestoreRequest,
    HouseholdBackupRestoreResponse,
    StagedBackupResponse,
)
from app.services.backups import (
    HOUSEHOLD_RESTORE_CONFIRMATION_PHRASE,
    bundle_summary,
    clear_staged_backup,
    load_staged_backup,
    restore_household_backup_bundle,
    stage_backup_upload,
)
from app.services.platform_admin import (
    create_managed_household,
    create_managed_user,
    delete_managed_household,
    rename_managed_household,
    remove_household_membership,
    send_managed_user_password_reset,
    update_managed_user,
    upsert_household_membership,
)

router = APIRouter(prefix="/platform-admin", tags=["platform-admin"])


def _serialize_household_summary(household: Household, membership_counts: dict[object, int]) -> AdminHouseholdSummary:
    sorted_memberships = sorted(
        [membership for membership in household.memberships if membership.user is not None and membership.role is not None],
        key=lambda item: ((item.user.display_name or item.user.email).lower(), item.user.email.lower()),
    )
    return AdminHouseholdSummary(
        external_id=household.external_id,
        name=household.name,
        membership_count=membership_counts.get(household.id, 0),
        memberships=[
            AdminHouseholdMemberSummary(
                membership_external_id=membership.external_id,
                user_external_id=membership.user.external_id,
                email=membership.user.email,
                display_name=membership.user.display_name,
                role=membership.role.code,
                is_active=membership.is_active,
            )
            for membership in sorted_memberships
        ],
    )


def _bad_request(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def _serialize_user_summary(user: User) -> AdminUserSummary:
    active_memberships = [
        membership
        for membership in user.memberships
        if membership.is_active and membership.household is not None and membership.role is not None
    ]
    sorted_memberships = sorted(active_memberships, key=lambda item: item.household.name.lower())
    return AdminUserSummary(
        external_id=user.external_id,
        email=user.email,
        display_name=user.display_name,
        is_active=user.is_active,
        platform_role=user.platform_role.code if user.platform_role else None,
        membership_count=len(sorted_memberships),
        memberships=[
            AdminUserMembershipSummary(
                household_external_id=membership.household.external_id,
                household_name=membership.household.name,
                role=membership.role.code,
                is_active=membership.is_active,
            )
            for membership in sorted_memberships
        ],
    )


@router.get("/overview", response_model=AdminOverviewResponse)
def get_overview(_: User = Depends(require_platform_admin), db: Session = Depends(get_db_session)):
    platform_admin_count = db.scalar(
        select(func.count(User.id))
        .join(Role, User.platform_role_id == Role.id)
        .where(Role.code == "platform_admin")
    )
    return AdminOverviewResponse(
        user_count=db.scalar(select(func.count(User.id))) or 0,
        platform_admin_count=platform_admin_count or 0,
        household_count=db.scalar(select(func.count(Household.id))) or 0,
        membership_count=db.scalar(select(func.count(Membership.id))) or 0,
    )


@router.get("/users", response_model=list[AdminUserSummary])
def list_users(_: User = Depends(require_platform_admin), db: Session = Depends(get_db_session)):
    users = db.scalars(
        select(User)
        .options(selectinload(User.platform_role))
        .options(selectinload(User.memberships).selectinload(Membership.household))
        .options(selectinload(User.memberships).selectinload(Membership.role))
        .order_by(User.email)
    ).all()
    return [_serialize_user_summary(user) for user in users]


@router.post("/users", response_model=AdminUserSummary, status_code=status.HTTP_201_CREATED)
def post_user(
    payload: CreateAdminUserRequest,
    current_user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db_session),
):
    try:
        user = create_managed_user(
            db,
            actor=current_user,
            email=payload.email,
            password=payload.password,
            display_name=payload.display_name,
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc

    refreshed_user = db.scalar(
        select(User)
        .where(User.id == user.id)
        .options(selectinload(User.platform_role))
        .options(selectinload(User.memberships).selectinload(Membership.household))
        .options(selectinload(User.memberships).selectinload(Membership.role))
    ) or user
    return _serialize_user_summary(refreshed_user)


@router.patch("/users/{user_external_id}", response_model=AdminUserSummary)
def patch_user(
    user_external_id: str,
    payload: UpdateAdminUserRequest,
    current_user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db_session),
):
    try:
        user = update_managed_user(
            db,
            actor=current_user,
            user_external_id=user_external_id,
            email=payload.email,
            display_name=payload.display_name,
            platform_role_code=payload.platform_role,
            memberships=[
                {
                    "household_external_id": membership.household_external_id,
                    "role": membership.role,
                }
                for membership in payload.memberships
            ],
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc

    return _serialize_user_summary(user)


@router.post("/users/{user_external_id}/send-password-reset", response_model=AdminActionResponse)
def post_user_password_reset(
    user_external_id: str,
    current_user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db_session),
):
    try:
        user = send_managed_user_password_reset(
            db,
            actor=current_user,
            user_external_id=user_external_id,
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc

    return AdminActionResponse(message=f"Sent a password reset email to {user.email}.")


@router.get("/households", response_model=list[AdminHouseholdSummary])
def list_households(_: User = Depends(require_platform_admin), db: Session = Depends(get_db_session)):
    membership_counts = {
        household_id: count
        for household_id, count in db.execute(
            select(Membership.household_id, func.count(Membership.id)).group_by(Membership.household_id)
        ).all()
    }

    households = db.scalars(
        select(Household)
        .options(selectinload(Household.memberships).selectinload(Membership.user))
        .options(selectinload(Household.memberships).selectinload(Membership.role))
        .order_by(Household.name)
    ).all()
    return [_serialize_household_summary(household, membership_counts) for household in households]


@router.post("/households", response_model=AdminHouseholdSummary, status_code=status.HTTP_201_CREATED)
def post_household(
    payload: CreateAdminHouseholdRequest,
    current_user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db_session),
):
    try:
        household = create_managed_household(
            db,
            actor=current_user,
            name=payload.name,
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc

    return AdminHouseholdSummary(
        external_id=household.external_id,
        name=household.name,
        membership_count=0,
        memberships=[],
    )


@router.patch("/households/{household_external_id}", response_model=AdminHouseholdSummary)
def patch_household(
    household_external_id: str,
    payload: UpdateAdminHouseholdRequest,
    current_user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db_session),
):
    try:
        household = rename_managed_household(
            db,
            actor=current_user,
            household_external_id=household_external_id,
            name=payload.name,
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc

    membership_count = db.scalar(
        select(func.count(Membership.id)).where(Membership.household_id == household.id)
    ) or 0
    refreshed_household = db.scalar(
        select(Household)
        .where(Household.id == household.id)
        .options(selectinload(Household.memberships).selectinload(Membership.user))
        .options(selectinload(Household.memberships).selectinload(Membership.role))
    ) or household
    return _serialize_household_summary(refreshed_household, {household.id: membership_count})


@router.post("/households/{household_external_id}/memberships", response_model=AdminHouseholdMemberSummary)
def post_household_membership(
    household_external_id: str,
    payload: CreateAdminMembershipRequest,
    current_user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db_session),
):
    try:
        membership = upsert_household_membership(
            db,
            actor=current_user,
            household_external_id=household_external_id,
            user_external_id=payload.user_external_id,
            role_code=payload.role,
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc

    membership = db.scalar(
        select(Membership)
        .where(Membership.id == membership.id)
        .options(selectinload(Membership.user), selectinload(Membership.role))
    ) or membership
    if membership.user is None or membership.role is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Membership load failed.")

    return AdminHouseholdMemberSummary(
        membership_external_id=membership.external_id,
        user_external_id=membership.user.external_id,
        email=membership.user.email,
        display_name=membership.user.display_name,
        role=membership.role.code,
        is_active=membership.is_active,
    )


@router.post(
    "/households/{household_external_id}/memberships/{membership_external_id}/remove",
    response_model=AdminActionResponse,
)
def post_remove_household_membership(
    household_external_id: str,
    membership_external_id: str,
    current_user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db_session),
):
    try:
        remove_household_membership(
            db,
            actor=current_user,
            household_external_id=household_external_id,
            membership_external_id=membership_external_id,
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc

    return AdminActionResponse(message="Household membership removed.")


@router.post("/households/{household_external_id}/delete", response_model=AdminActionResponse)
def post_delete_household(
    household_external_id: str,
    payload: DeleteAdminHouseholdRequest,
    current_user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db_session),
):
    try:
        delete_managed_household(
            db,
            actor=current_user,
            household_external_id=household_external_id,
            confirm_household_name=payload.confirm_household_name,
            acknowledge_last_household_deletion=payload.acknowledge_last_household_deletion,
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc

    return AdminActionResponse(message="Household deleted.")


@router.post("/households/restore-upload", response_model=StagedBackupResponse)
async def post_household_restore_upload(
    file: UploadFile = File(...),
    _: User = Depends(require_platform_admin),
    db: Session = Depends(get_db_session),
):
    try:
        staged = await stage_backup_upload(
            db,
            settings=get_settings(),
            upload=file,
            allowed_restore_scopes={"household"},
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc

    return StagedBackupResponse(
        stage_id=staged.stage_id,
        original_filename=staged.original_filename,
        size_bytes=staged.size_bytes,
        uploaded_at=staged.uploaded_at,
        quarantine_path=staged.quarantine_path,
        supported_for_restore=staged.supported_for_restore,
        warnings=list(staged.warnings),
        bundle=BackupBundleSummary.model_validate(bundle_summary(staged.bundle)),
    )


@router.post("/households/restore", response_model=HouseholdBackupRestoreResponse)
def post_household_restore(
    payload: HouseholdBackupRestoreRequest,
    current_user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db_session),
):
    if payload.confirmation_phrase.strip() != HOUSEHOLD_RESTORE_CONFIRMATION_PHRASE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Enter the exact confirmation phrase: {HOUSEHOLD_RESTORE_CONFIRMATION_PHRASE}",
        )

    try:
        bundle = load_staged_backup(get_settings(), stage_id=payload.stage_id)
        restored_bundle, warnings = restore_household_backup_bundle(
            db,
            bundle=bundle,
            actor=current_user,
            target_household_name=payload.target_household_name,
        )
        clear_staged_backup(get_settings(), stage_id=payload.stage_id)
    except ValueError as exc:
        raise _bad_request(exc) from exc

    return HouseholdBackupRestoreResponse(
        restored=True,
        message="Household restored into a new household. Review memberships, pantry data, and any compatibility warnings before using it.",
        warnings=list(warnings),
        bundle=BackupBundleSummary.model_validate(restored_bundle),
    )

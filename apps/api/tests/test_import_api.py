from __future__ import annotations

import json
from decimal import Decimal

from sqlalchemy import select

from app.domain.roles import HOUSEHOLD_ADMIN_ROLE
from app.models.audit_event import AuditEvent
from app.models.import_job import ImportJob
from app.models.product import Product
from app.models.product_alias import ProductAlias
from app.models.stock_lot import StockLot
from app.services.auth import create_household, create_membership, create_user
from app.services.import_processing import process_next_import_job
from app.services.platform_features import FLAG_REVIEWED_IMPORTS, upsert_feature_flag


PASSWORD = "correct horse battery"


def login(client, *, email: str, password: str = PASSWORD) -> None:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200


def create_member_household(db_session, *, email: str, household_name: str):
    user = create_user(db_session, email=email, password=PASSWORD, display_name=email.split("@")[0].title())
    household = create_household(db_session, name=household_name)
    create_membership(
        db_session,
        user=user,
        household=household,
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    return user, household


def create_location_group(client, household_external_id: str, name: str) -> dict:
    response = client.post(
        f"/api/households/{household_external_id}/location-groups",
        json={"name": name},
    )
    assert response.status_code == 201
    return response.json()


def create_location(client, household_external_id: str, location_group_external_id: str, name: str) -> dict:
    response = client.post(
        f"/api/households/{household_external_id}/locations",
        json={"location_group_external_id": location_group_external_id, "name": name},
    )
    assert response.status_code == 201
    return response.json()


def create_product(client, household_external_id: str, **payload) -> dict:
    response = client.post(f"/api/households/{household_external_id}/products", json=payload)
    assert response.status_code == 201
    return response.json()


def test_import_upload_worker_review_and_confirm_flow(client, db_session):
    _, household = create_member_household(
        db_session,
        email="imports@example.com",
        household_name="Import Household",
    )
    login(client, email="imports@example.com")

    group = create_location_group(client, household.external_id, "Pantry")
    location = create_location(client, household.external_id, group["external_id"], "Shelf")
    pasta = create_product(
        client,
        household.external_id,
        name="Pasta",
        default_unit="count",
        aliases=["Dry pasta"],
        barcodes=["00123"],
    )
    tomatoes = create_product(
        client,
        household.external_id,
        name="Tomatoes",
        default_unit="can",
        aliases=[],
        barcodes=[],
    )
    spice = create_product(
        client,
        household.external_id,
        name="Spice Blend",
        default_unit="jar",
        aliases=[],
        barcodes=[],
    )

    upload_response = client.post(
        f"/api/households/{household.external_id}/imports/uploads",
        data={
            "source_type": "online_order",
            "occurred_on": "2026-04-01",
            "note": "Weekly order",
        },
        files={
            "file": (
                "weekly-order.json",
                json.dumps(
                    {
                        "lines": [
                            {"name": "Dry pasta", "quantity": "2.000", "unit": "count", "barcode": "00123"},
                            {"name": "Tomatoes", "quantity": "3.000", "unit": "can"},
                            {"name": "House Blend", "quantity": "1.000", "unit": "jar"},
                        ]
                    }
                ),
                "application/json",
            )
        },
    )
    assert upload_response.status_code == 201
    upload_payload = upload_response.json()["import_job"]
    assert upload_payload["status"] == "queued"
    assert upload_payload["counts"]["line_count"] == 0

    assert process_next_import_job() is True

    detail_response = client.get(
        f"/api/households/{household.external_id}/imports/{upload_payload['external_id']}"
    )
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()["import_job"]
    assert detail_payload["status"] == "needs_review"
    assert detail_payload["counts"]["line_count"] == 3
    assert detail_payload["counts"]["matched_line_count"] == 2
    assert detail_payload["counts"]["unresolved_line_count"] == 1

    unresolved_line = next(line for line in detail_payload["lines"] if line["status"] == "unresolved")
    barcode_line = next(line for line in detail_payload["lines"] if line["raw_label"] == "Dry pasta")
    assert barcode_line["match_basis"] == "barcode_exact"

    blocked_confirm = client.post(
        f"/api/households/{household.external_id}/imports/{upload_payload['external_id']}/confirm",
        json={"location_external_id": location["external_id"]},
    )
    assert blocked_confirm.status_code == 400
    assert blocked_confirm.json()["detail"] == "Resolve or ignore all remaining import lines before confirming."

    review_response = client.put(
        f"/api/households/{household.external_id}/imports/{upload_payload['external_id']}/lines/{unresolved_line['external_id']}",
        json={
            "product_external_id": spice["external_id"],
            "status": "matched",
            "note": "Manual review",
        },
    )
    assert review_response.status_code == 200
    reviewed_payload = review_response.json()["import_job"]
    assert reviewed_payload["counts"]["matched_line_count"] == 3
    assert reviewed_payload["ready_to_confirm"] is True

    confirm_response = client.post(
        f"/api/households/{household.external_id}/imports/{upload_payload['external_id']}/confirm",
        json={
            "location_external_id": location["external_id"],
            "purchased_on": "2026-04-01",
        },
    )
    assert confirm_response.status_code == 200
    confirmed_payload = confirm_response.json()["import_job"]
    assert confirmed_payload["status"] == "confirmed"
    assert confirmed_payload["counts"]["confirmed_line_count"] == 3
    assert all(line["status"] == "confirmed" for line in confirmed_payload["lines"])

    stored_lots = db_session.scalars(select(StockLot).where(StockLot.household_id == household.id)).all()
    assert len(stored_lots) == 3
    lot_units = sorted(lot.unit for lot in stored_lots)
    assert lot_units == ["can", "count", "jar"]

    learned_alias = db_session.scalar(
        select(ProductAlias)
        .where(ProductAlias.household_id == household.id)
        .where(ProductAlias.normalized_name == "house blend")
    )
    assert learned_alias is not None
    learned_alias_product = db_session.scalar(select(Product).where(Product.id == learned_alias.product_id))
    assert learned_alias_product is not None
    assert learned_alias_product.external_id == spice["external_id"]

    audit_actions = db_session.scalars(
        select(AuditEvent.action)
        .where(AuditEvent.household_id == household.id)
        .order_by(AuditEvent.occurred_at.asc())
    ).all()
    assert "import.created" in audit_actions
    assert "import.review_ready" in audit_actions
    assert "import.line.reviewed" in audit_actions
    assert "import.confirmed" in audit_actions


def test_import_worker_marks_unsupported_file_types_failed(client, db_session):
    _, household = create_member_household(
        db_session,
        email="import-failure@example.com",
        household_name="Failure Household",
    )
    login(client, email="import-failure@example.com")

    upload_response = client.post(
        f"/api/households/{household.external_id}/imports/uploads",
        data={"source_type": "receipt"},
        files={"file": ("receipt.pdf", b"%PDF-1.4\n%stub", "application/pdf")},
    )
    assert upload_response.status_code == 201
    import_external_id = upload_response.json()["import_job"]["external_id"]

    assert process_next_import_job() is True

    detail_response = client.get(f"/api/households/{household.external_id}/imports/{import_external_id}")
    assert detail_response.status_code == 200
    payload = detail_response.json()["import_job"]
    assert payload["status"] == "failed"
    assert payload["failure_message"] == "Parsing for PDF and image imports is not implemented yet."

    failure_event = db_session.scalar(
        select(AuditEvent)
        .where(AuditEvent.target_external_id == import_external_id)
        .where(AuditEvent.action == "import.failed")
    )
    assert failure_event is not None


def test_import_worker_skips_empty_rows_and_flags_invalid_values_for_review(client, db_session):
    _, household = create_member_household(
        db_session,
        email="import-edge@example.com",
        household_name="Edge Imports",
    )
    login(client, email="import-edge@example.com")

    create_product(
        client,
        household.external_id,
        name="Pasta",
        default_unit="count",
        aliases=[],
        barcodes=[],
    )

    upload_response = client.post(
        f"/api/households/{household.external_id}/imports/uploads",
        data={"source_type": "structured_import"},
        files={
            "file": (
                "edge-cases.csv",
                "name,quantity,unit,purchased_on\nPasta,0,count,2026-04-01\n,,,\n,2,,bad-date\n",
                "text/csv",
            )
        },
    )
    assert upload_response.status_code == 201

    assert process_next_import_job() is True

    detail_response = client.get(
        f"/api/households/{household.external_id}/imports/{upload_response.json()['import_job']['external_id']}"
    )
    assert detail_response.status_code == 200
    payload = detail_response.json()["import_job"]
    assert payload["status"] == "needs_review"
    assert payload["counts"]["line_count"] == 2
    assert payload["counts"]["needs_review_line_count"] == 2

    first_line = payload["lines"][0]
    second_line = payload["lines"][1]
    assert first_line["quantity"] == "1.000"
    assert "defaulted to 1.000" in first_line["note"]
    assert second_line["raw_label"] == "row:4"
    assert "Line label was missing" in second_line["note"]
    assert "Purchased date was invalid" in second_line["note"]


def test_import_endpoints_enforce_household_scoping(client, db_session):
    _, allowed_household = create_member_household(
        db_session,
        email="import-scope@example.com",
        household_name="Allowed Imports",
    )
    denied_household = create_household(db_session, name="Denied Imports")
    login(client, email="import-scope@example.com")

    allowed = client.get(f"/api/households/{allowed_household.external_id}/imports")
    denied = client.get(f"/api/households/{denied_household.external_id}/imports")

    assert allowed.status_code == 200
    assert denied.status_code == 404


def test_reviewed_imports_can_be_disabled_by_feature_flag(client, db_session):
    _, household = create_member_household(
        db_session,
        email="imports-flag@example.com",
        household_name="Import Flag Household",
    )
    upsert_feature_flag(
        db_session,
        flag_key=FLAG_REVIEWED_IMPORTS,
        scope_type="household",
        scope_key=household.external_id,
        is_enabled=False,
        note="Disabled for maintenance.",
    )
    login(client, email="imports-flag@example.com")

    response = client.get(f"/api/households/{household.external_id}/imports")
    assert response.status_code == 403
    assert "disabled" in response.json()["detail"].lower()

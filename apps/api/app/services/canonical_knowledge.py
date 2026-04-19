from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.canonical_alias import CanonicalAlias
from app.models.canonical_item import CanonicalItem
from app.models.household import Household
from app.models.product import Product
from app.models.product_canonical_link import ProductCanonicalLink
from app.models.user import User
from app.services.audit import record_audit_event
from app.services.pantry_normalization import expand_lookup_name_variants, normalize_barcode, normalize_lookup_name

CANONICAL_ALIAS_TYPE_BARCODE = "barcode"
CANONICAL_ALIAS_TYPE_NAME = "name"
CANONICAL_STATUS_PENDING = "pending"
CANONICAL_STATUS_VERIFIED = "verified"
CANONICAL_MATCH_BARCODE = "barcode_exact"
CANONICAL_MATCH_ENRICHMENT = "enrichment_name"
CANONICAL_MATCH_NAME = "product_name"
CANONICAL_MATCH_ALIAS = "product_alias"
CANONICAL_MATCH_PROPOSAL = "proposal"
CANONICAL_SOURCE_PRODUCT = "product"
CANONICAL_SOURCE_PRODUCT_ALIAS = "product_alias"
CANONICAL_SOURCE_PRODUCT_BARCODE = "product_barcode"
CANONICAL_SOURCE_OPEN_FOOD_FACTS = "open_food_facts"
CANONICAL_SOURCE_SEED = "canonical_seed"


@dataclass(frozen=True)
class CanonicalSeedDefinition:
    name: str
    aliases: tuple[str, ...] = ()
    barcodes: tuple[str, ...] = ()


DEFAULT_CANONICAL_ITEMS: tuple[CanonicalSeedDefinition, ...] = (
    CanonicalSeedDefinition(name="Pasta", aliases=("Spaghetti",)),
    CanonicalSeedDefinition(name="Tomatoes", aliases=("Chopped Tomatoes", "Tomato")),
    CanonicalSeedDefinition(name="Rice"),
    CanonicalSeedDefinition(name="Milk"),
    CanonicalSeedDefinition(name="Oats"),
    CanonicalSeedDefinition(name="Mayonnaise", aliases=("Mayo", "Tesco Mayonnaise", "Tesco Mayo")),
)


def _load_product_for_canonical_match(db: Session, *, product_id) -> Product:
    return db.scalar(
        select(Product)
        .where(Product.id == product_id)
        .options(selectinload(Product.aliases))
        .options(selectinload(Product.barcodes))
        .options(selectinload(Product.enrichments))
        .options(selectinload(Product.canonical_link).selectinload(ProductCanonicalLink.canonical_item))
    )


def _get_alias(
    db: Session,
    *,
    household_id,
    alias_type: str,
    normalized_value: str,
) -> CanonicalAlias | None:
    return db.scalar(
        select(CanonicalAlias)
        .where(CanonicalAlias.household_id == household_id)
        .where(CanonicalAlias.alias_type == alias_type)
        .where(CanonicalAlias.normalized_value == normalized_value)
        .options(selectinload(CanonicalAlias.canonical_item))
    )


def _review_rank(review_status: str) -> int:
    if review_status == CANONICAL_STATUS_VERIFIED:
        return 2
    if review_status == CANONICAL_STATUS_PENDING:
        return 1
    return 0


def _ensure_alias(
    db: Session,
    *,
    household: Household,
    canonical_item: CanonicalItem,
    alias_type: str,
    value: str,
    review_status: str,
    source_name: str,
    provenance_payload: dict[str, object],
) -> CanonicalAlias:
    normalized_value = normalize_barcode(value) if alias_type == CANONICAL_ALIAS_TYPE_BARCODE else normalize_lookup_name(value)
    existing = _get_alias(
        db,
        household_id=household.id,
        alias_type=alias_type,
        normalized_value=normalized_value,
    )
    if existing is not None:
        if existing.canonical_item_id == canonical_item.id:
            if _review_rank(review_status) >= _review_rank(existing.review_status):
                existing.value = value
                existing.review_status = review_status
                existing.source_name = source_name
                existing.provenance_payload = provenance_payload
                db.add(existing)
                db.flush()
        elif _review_rank(review_status) > _review_rank(existing.review_status):
            existing.canonical_item_id = canonical_item.id
            existing.value = value
            existing.review_status = review_status
            existing.source_name = source_name
            existing.provenance_payload = provenance_payload
            db.add(existing)
            db.flush()
        return existing

    alias = CanonicalAlias(
        household_id=household.id,
        canonical_item_id=canonical_item.id,
        alias_type=alias_type,
        value=value,
        normalized_value=normalized_value,
        review_status=review_status,
        source_name=source_name,
        provenance_payload=provenance_payload,
    )
    db.add(alias)
    db.flush()
    return alias


def ensure_canonical_item(
    db: Session,
    *,
    household: Household,
    name: str,
    review_status: str,
    source_name: str,
    actor: User | None = None,
    aliases: list[str] | None = None,
    barcodes: list[str] | None = None,
    provenance_payload: dict[str, object] | None = None,
) -> CanonicalItem:
    normalized_name = normalize_lookup_name(name)
    existing = db.scalar(
        select(CanonicalItem)
        .where(CanonicalItem.household_id == household.id)
        .where(CanonicalItem.normalized_name == normalized_name)
    )
    if existing is None:
        existing = CanonicalItem(
            household_id=household.id,
            name=name,
            normalized_name=normalized_name,
            review_status=review_status,
            source_name=source_name,
            provenance_payload=provenance_payload or {},
        )
        db.add(existing)
        db.flush()
        record_audit_event(
            db,
            household=household,
            actor=actor,
            action="canonical_item.saved",
            target_type="canonical_item",
            target_external_id=existing.external_id,
            event_metadata={
                "name": existing.name,
                "review_status": existing.review_status,
                "source_name": existing.source_name,
            },
        )
    else:
        existing.name = name
        existing.normalized_name = normalized_name
        existing.review_status = review_status
        if provenance_payload:
            existing.provenance_payload = provenance_payload
        if source_name:
            existing.source_name = source_name
        db.add(existing)

    _ensure_alias(
        db,
        household=household,
        canonical_item=existing,
        alias_type=CANONICAL_ALIAS_TYPE_NAME,
        value=name,
        review_status=review_status,
        source_name=source_name,
        provenance_payload=provenance_payload or {},
    )

    for alias_value in aliases or []:
        _ensure_alias(
            db,
            household=household,
            canonical_item=existing,
            alias_type=CANONICAL_ALIAS_TYPE_NAME,
            value=alias_value,
            review_status=review_status,
            source_name=source_name,
            provenance_payload=provenance_payload or {},
        )

    for barcode_value in barcodes or []:
        _ensure_alias(
            db,
            household=household,
            canonical_item=existing,
            alias_type=CANONICAL_ALIAS_TYPE_BARCODE,
            value=barcode_value,
            review_status=review_status,
            source_name=source_name,
            provenance_payload=provenance_payload or {},
        )

    db.flush()
    return existing


def bootstrap_default_canonical_items(
    db: Session,
    *,
    household: Household,
    actor: User | None = None,
) -> None:
    for definition in DEFAULT_CANONICAL_ITEMS:
        ensure_canonical_item(
            db,
            household=household,
            actor=actor,
            name=definition.name,
            aliases=list(definition.aliases),
            barcodes=list(definition.barcodes),
            review_status=CANONICAL_STATUS_VERIFIED,
            source_name=CANONICAL_SOURCE_SEED,
            provenance_payload={"bootstrap": True},
        )


def resolve_canonical_match_inputs(
    *,
    name: str | None,
    aliases: list[str] | None = None,
    barcode: str | None = None,
) -> list[tuple[str, str, str]]:
    inputs: list[tuple[str, str, str]] = []
    if barcode and barcode.strip():
        inputs.append((normalize_barcode(barcode), CANONICAL_MATCH_BARCODE, CANONICAL_SOURCE_PRODUCT_BARCODE))

    seen_names: set[str] = set()
    for value, match_method, source_name in (
        [(name or "", CANONICAL_MATCH_NAME, CANONICAL_SOURCE_PRODUCT)]
        + [(alias, CANONICAL_MATCH_ALIAS, CANONICAL_SOURCE_PRODUCT_ALIAS) for alias in aliases or []]
    ):
        if not value or not value.strip():
            continue
        for normalized_value in expand_lookup_name_variants(value):
            if normalized_value in seen_names:
                continue
            seen_names.add(normalized_value)
            inputs.append((normalized_value, match_method, source_name))
    return inputs


def resolve_canonical_item_for_inputs(
    db: Session,
    *,
    household: Household,
    name: str | None,
    aliases: list[str] | None = None,
    barcode: str | None = None,
    review_status: str = CANONICAL_STATUS_VERIFIED,
) -> tuple[CanonicalItem | None, str | None, str | None]:
    for normalized_value, match_method, source_name in resolve_canonical_match_inputs(
        name=name,
        aliases=aliases,
        barcode=barcode,
    ):
        alias_type = CANONICAL_ALIAS_TYPE_BARCODE if match_method == CANONICAL_MATCH_BARCODE else CANONICAL_ALIAS_TYPE_NAME
        matched_alias = _get_alias(
            db,
            household_id=household.id,
            alias_type=alias_type,
            normalized_value=normalized_value,
        )
        if matched_alias is not None and matched_alias.review_status == review_status:
            return matched_alias.canonical_item, match_method, source_name
    return None, None, None


def serialize_product_canonical_summary(product: Product) -> dict[str, object] | None:
    link = product.canonical_link
    if link is None:
        return None

    item = link.canonical_item
    return {
        "link_external_id": link.external_id,
        "link_status": link.link_status,
        "match_method": link.match_method,
        "source_name": link.source_name,
        "canonical_item": {
            "external_id": item.external_id,
            "name": item.name,
            "review_status": item.review_status,
            "item_type": item.item_type,
        },
    }


def _candidate_name_inputs(product: Product) -> list[tuple[str, str, str]]:
    inputs: list[tuple[str, str, str]] = [(product.name, CANONICAL_MATCH_NAME, CANONICAL_SOURCE_PRODUCT)]
    inputs.extend((alias.name, CANONICAL_MATCH_ALIAS, CANONICAL_SOURCE_PRODUCT_ALIAS) for alias in product.aliases)
    for enrichment in product.enrichments:
        if enrichment.source_product_name:
            inputs.append(
                (
                    enrichment.source_product_name,
                    CANONICAL_MATCH_ENRICHMENT,
                    enrichment.source_name,
                )
            )
    return inputs


def _match_existing_canonical_item(
    db: Session,
    *,
    household: Household,
    product: Product,
    review_status: str,
) -> tuple[CanonicalItem | None, str | None, str | None]:
    for barcode in product.barcodes:
        matched_alias = _get_alias(
            db,
            household_id=household.id,
            alias_type=CANONICAL_ALIAS_TYPE_BARCODE,
            normalized_value=barcode.normalized_value,
        )
        if matched_alias is not None and matched_alias.review_status == review_status:
            return matched_alias.canonical_item, CANONICAL_MATCH_BARCODE, matched_alias.source_name

    for value, match_method, source_name in _candidate_name_inputs(product):
        for normalized_value in expand_lookup_name_variants(value):
            matched_alias = _get_alias(
                db,
                household_id=household.id,
                alias_type=CANONICAL_ALIAS_TYPE_NAME,
                normalized_value=normalized_value,
            )
            if matched_alias is not None and matched_alias.review_status == review_status:
                return matched_alias.canonical_item, match_method, source_name

    return None, None, None


def _capture_product_signals(
    db: Session,
    *,
    household: Household,
    canonical_item: CanonicalItem,
    product: Product,
) -> None:
    _ensure_alias(
        db,
        household=household,
        canonical_item=canonical_item,
        alias_type=CANONICAL_ALIAS_TYPE_NAME,
        value=product.name,
        review_status=CANONICAL_STATUS_PENDING,
        source_name=CANONICAL_SOURCE_PRODUCT,
        provenance_payload={"product_external_id": product.external_id},
    )
    for alias in product.aliases:
        _ensure_alias(
            db,
            household=household,
            canonical_item=canonical_item,
            alias_type=CANONICAL_ALIAS_TYPE_NAME,
            value=alias.name,
            review_status=CANONICAL_STATUS_PENDING,
            source_name=CANONICAL_SOURCE_PRODUCT_ALIAS,
            provenance_payload={"product_external_id": product.external_id},
        )
    for barcode in product.barcodes:
        _ensure_alias(
            db,
            household=household,
            canonical_item=canonical_item,
            alias_type=CANONICAL_ALIAS_TYPE_BARCODE,
            value=barcode.value,
            review_status=CANONICAL_STATUS_PENDING,
            source_name=CANONICAL_SOURCE_PRODUCT_BARCODE,
            provenance_payload={"product_external_id": product.external_id},
        )
    for enrichment in product.enrichments:
        if enrichment.source_product_name:
            _ensure_alias(
                db,
                household=household,
                canonical_item=canonical_item,
                alias_type=CANONICAL_ALIAS_TYPE_NAME,
                value=enrichment.source_product_name,
                review_status=CANONICAL_STATUS_PENDING,
                source_name=enrichment.source_name or CANONICAL_SOURCE_OPEN_FOOD_FACTS,
                provenance_payload={
                    "product_external_id": product.external_id,
                    "source_product_id": enrichment.source_product_id,
                },
            )


def sync_product_canonical_link(
    db: Session,
    *,
    household: Household,
    actor: User | None,
    product: Product,
) -> ProductCanonicalLink:
    db.flush()
    loaded_product = _load_product_for_canonical_match(db, product_id=product.id) or product
    matched_item, match_method, source_name = _match_existing_canonical_item(
        db,
        household=household,
        product=loaded_product,
        review_status=CANONICAL_STATUS_VERIFIED,
    )
    link_status = CANONICAL_STATUS_VERIFIED

    if matched_item is None:
        matched_item, match_method, source_name = _match_existing_canonical_item(
            db,
            household=household,
            product=loaded_product,
            review_status=CANONICAL_STATUS_PENDING,
        )
        link_status = CANONICAL_STATUS_PENDING

    if matched_item is None:
        matched_item = ensure_canonical_item(
            db,
            household=household,
            actor=actor,
            name=loaded_product.name,
            review_status=CANONICAL_STATUS_PENDING,
            source_name=CANONICAL_SOURCE_PRODUCT,
            provenance_payload={"product_external_id": loaded_product.external_id},
        )
        match_method = CANONICAL_MATCH_PROPOSAL
        source_name = CANONICAL_SOURCE_PRODUCT
        link_status = CANONICAL_STATUS_PENDING

    _capture_product_signals(
        db,
        household=household,
        canonical_item=matched_item,
        product=loaded_product,
    )

    link = db.scalar(
        select(ProductCanonicalLink)
        .where(ProductCanonicalLink.product_id == loaded_product.id)
        .options(selectinload(ProductCanonicalLink.canonical_item))
    )
    if link is None:
        link = ProductCanonicalLink(
            household_id=household.id,
            product_id=loaded_product.id,
            canonical_item_id=matched_item.id,
            link_status=link_status,
            match_method=match_method or CANONICAL_MATCH_PROPOSAL,
            source_name=source_name,
            provenance_payload={"product_external_id": loaded_product.external_id},
        )
        db.add(link)
    else:
        link.canonical_item_id = matched_item.id
        link.link_status = link_status
        link.match_method = match_method or CANONICAL_MATCH_PROPOSAL
        link.source_name = source_name
        link.provenance_payload = {"product_external_id": loaded_product.external_id}
        db.add(link)

    db.flush()
    record_audit_event(
        db,
        household=household,
        actor=actor,
        action="product.canonical_linked",
        target_type="product",
        target_external_id=loaded_product.external_id,
        event_metadata={
            "canonical_item_external_id": matched_item.external_id,
            "canonical_item_name": matched_item.name,
            "link_status": link.link_status,
            "match_method": link.match_method,
            "source_name": link.source_name,
        },
    )
    return link


def get_linked_product_for_canonical_item(
    db: Session,
    *,
    household: Household,
    canonical_item_id,
    link_status: str = CANONICAL_STATUS_VERIFIED,
) -> Product | None:
    return db.scalar(
        select(Product)
        .join(ProductCanonicalLink, ProductCanonicalLink.product_id == Product.id)
        .where(Product.household_id == household.id)
        .where(ProductCanonicalLink.canonical_item_id == canonical_item_id)
        .where(ProductCanonicalLink.link_status == link_status)
        .options(selectinload(Product.aliases), selectinload(Product.barcodes))
        .order_by(Product.name.asc())
    )


def get_linked_product_for_canonical_candidate(
    db: Session,
    *,
    household: Household,
    name: str | None,
    aliases: list[str] | None = None,
    barcode: str | None = None,
) -> tuple[Product | None, CanonicalItem | None, str | None]:
    matched_item, match_method, _source_name = resolve_canonical_item_for_inputs(
        db,
        household=household,
        name=name,
        aliases=aliases,
        barcode=barcode,
        review_status=CANONICAL_STATUS_VERIFIED,
    )
    if matched_item is None:
        return None, None, None
    linked_product = get_linked_product_for_canonical_item(
        db,
        household=household,
        canonical_item_id=matched_item.id,
        link_status=CANONICAL_STATUS_VERIFIED,
    )
    return linked_product, matched_item, match_method


def relink_household_products_to_canonical_items(
    db: Session,
    *,
    household: Household,
    actor: User | None,
) -> int:
    products = db.scalars(
        select(Product)
        .where(Product.household_id == household.id)
        .order_by(Product.created_at.asc())
    ).all()
    for product in products:
        sync_product_canonical_link(
            db,
            household=household,
            actor=actor,
            product=product,
        )
    return len(products)


def get_linked_product_for_canonical_name(
    db: Session,
    *,
    household: Household,
    ingredient_name: str,
) -> Product | None:
    alias = _get_alias(
        db,
        household_id=household.id,
        alias_type=CANONICAL_ALIAS_TYPE_NAME,
        normalized_value=normalize_lookup_name(ingredient_name),
    )
    if alias is None or alias.review_status != CANONICAL_STATUS_VERIFIED:
        return None

    return db.scalar(
        select(Product)
        .join(ProductCanonicalLink, ProductCanonicalLink.product_id == Product.id)
        .where(Product.household_id == household.id)
        .where(ProductCanonicalLink.canonical_item_id == alias.canonical_item_id)
        .where(ProductCanonicalLink.link_status == CANONICAL_STATUS_VERIFIED)
        .options(selectinload(Product.aliases), selectinload(Product.barcodes))
        .order_by(Product.name.asc())
    )

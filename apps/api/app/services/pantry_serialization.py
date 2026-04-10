from __future__ import annotations

from app.models.product import Product
from app.services.product_enrichment import serialize_product_enrichment, get_primary_enrichment
from app.services.product_intelligence import (
    get_primary_product_intelligence,
    serialize_product_intelligence,
)


def serialize_product_enrichment_summary(product: Product):
    return serialize_product_enrichment(get_primary_enrichment(product))


def serialize_product_intelligence_summary(product: Product):
    return serialize_product_intelligence(get_primary_product_intelligence(product), product=product)

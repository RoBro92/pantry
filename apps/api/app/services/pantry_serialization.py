from __future__ import annotations

from app.models.product import Product
from app.services.product_enrichment import serialize_product_enrichment, get_primary_enrichment


def serialize_product_enrichment_summary(product: Product):
    return serialize_product_enrichment(get_primary_enrichment(product))

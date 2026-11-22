"""Public Shopify storefront data. Every Shopify store serves /meta.json."""

import json

import httpx

from app.tools import http


def check_store(domain: str) -> dict | None:
    """{name, city, province, country, products, currency, ships_to} or None if not Shopify."""
    try:
        status, text = http.get(f"https://{domain}/meta.json")
    except (http.Blocked, httpx.HTTPError):  # blocked, down or too slow: treat as not a store
        return None
    if status != 200:
        return None
    try:
        meta = json.loads(text)
    except ValueError:
        return None
    if not isinstance(meta, dict) or "name" not in meta:
        return None
    return {
        "name": meta.get("name", ""),
        "city": meta.get("city") or "",
        "province": meta.get("province") or "",
        "country": meta.get("country") or "",
        "products": meta.get("published_products_count") or 0,
        "currency": meta.get("currency") or "",
        "ships_to": meta.get("ships_to_countries") or [],
        "url": f"https://{domain}/meta.json",
    }

"""Transparent, factual rules used to select report highlights.

These rules classify observed artifacts for review; they do not determine intent
or guilt. The returned rule IDs are included in reports so an examiner can see
why an item was selected.
"""

from __future__ import annotations

from typing import Any


BROWSER_RULES: tuple[dict[str, Any], ...] = (
    {
        "id": "browser_search_engine",
        "name": "Search engine activity",
        "terms": ("bing", "google", "yahoo"),
    },
    {
        "id": "browser_search_activity",
        "name": "Search activity",
        "terms": ("search",),
    },
    {
        "id": "browser_disappearance_terms",
        "name": "Disappearance-related term",
        "terms": ("disappear",),
    },
    {
        "id": "browser_identity_terms",
        "name": "Identity-related term",
        "terms": ("identity", "id theft"),
    },
    {
        "id": "browser_vehicle_terms",
        "name": "Vehicle-related term",
        "terms": ("car",),
    },
    {
        "id": "browser_printer_terms",
        "name": "Printer-related term",
        "terms": ("printer",),
    },
    {
        "id": "browser_harassment_terms",
        "name": "Harassment-related term",
        "terms": ("harass",),
    },
)

DOCUMENT_RULES: tuple[dict[str, Any], ...] = (
    {
        "id": "document_bctextencoder",
        "name": "BCTextEncoder indicator",
        "terms": ("encoded", "bctextencoder"),
    },
    {
        "id": "document_recycle_bin",
        "name": "Recycle Bin path",
        "terms": ("recycle", "$r"),
    },
    {
        "id": "document_user_path",
        "name": "User profile path",
        "terms": ("users",),
    },
)


def matching_rules(value: str, rules: tuple[dict[str, Any], ...]) -> list[dict[str, str]]:
    """Return named rules matching a value, preserving rule order."""
    lower = (value or "").lower()
    return [
        {"id": rule["id"], "name": rule["name"]}
        for rule in rules
        if any(term in lower for term in rule["terms"])
    ]


def browser_rules(url: str) -> list[dict[str, str]]:
    return matching_rules(url, BROWSER_RULES)


def document_rules(path: str) -> list[dict[str, str]]:
    return matching_rules(path, DOCUMENT_RULES)

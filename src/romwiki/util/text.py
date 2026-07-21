"""Shared text-normalization helpers."""

from __future__ import annotations

import re
import unicodedata


def name_slug(value: str) -> str:
    """Slugify a ROM-derived display name into a URL/lookup-safe key."""
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", normalized.casefold()).strip("-")


def title_case_slug(slug: str) -> str:
    """Turn a hyphenated slug into a Title Case display name."""
    return " ".join(part.capitalize() for part in slug.split("-"))

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


def normalize_display_name(value: str) -> str:
    """Recapitalize an all-caps ROM display name ("MR. MIME" -> "Mr. Mime").

    Vanilla Gen IV stores Pokémon names in upper case while hacks often
    recapitalize them; normalizing both sides keeps display names readable
    and avoids spurious capitalization-only differences in comparisons.
    Names that already contain lowercase letters are returned unchanged.
    """
    if not value.isupper():
        return value
    characters = []
    start_of_word = True
    for character in value:
        if character.isalpha():
            characters.append(
                character.upper() if start_of_word else character.lower()
            )
            start_of_word = False
        else:
            characters.append(character)
            # Apostrophes continue a word ("FARFETCH'D" -> "Farfetch'd");
            # every other separator starts one ("HO-OH" -> "Ho-Oh").
            start_of_word = character not in "'’"
    return "".join(characters)

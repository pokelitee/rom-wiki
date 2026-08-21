"""Trivial trainer-variant resolution for the base FireRed/LeafGreen retail games.

The base games have no hack-specific trainer variants (starter-branch rivals,
difficulty modes, rematch stages, etc.) decoded yet, so this unconditionally
reports every mechanic as unresolved and no battle families -- unlike every
NDS engine's `battle_variants.py`, there is no `_CONTRACTS` allowlist here
yet. A hack profile (e.g. Fire Red Omega) that needs real variant coverage
adds its own verified contract and decoding logic to this file when that
work starts, the same way `sacred-gold`/`blaze-black` extended their base
engines' `battle_variants.py`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from romwiki.schema.trainers import unresolved_trainer_variant_support


def resolve_trainer_variants(
    profile_id: str,
    parameters: Mapping[str, Any],
    records: Sequence[Mapping[str, Any]],
    *,
    selector_data: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "trainer_variant_support": unresolved_trainer_variant_support(),
        "battle_families": [],
    }

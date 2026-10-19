from __future__ import annotations

from collections.abc import Mapping

from romwiki.engines.registry import (
    DATASET_KINDS,
    DEFAULT_REQUIRED_DATASET_KINDS,
    get_engine,
)
from romwiki.profiles.models import GameProfile
from romwiki.util.errors import ProfileError

_SECTION_LAYOUT_REQUIREMENTS: dict[str, tuple[tuple[str, ...], ...]] = {
    # Each inner tuple lists keys that must ALL be present (in `profile.layout`
    # or `profile.parameters`, see `_contains_all`); the outer tuple lists
    # alternative ways to satisfy the section. NDS-style engines locate a
    # domain via a `[layout]` archive path alias (e.g. `personal = "a/0/0/2"`);
    # a flat, offset-addressed platform (e.g. Game Boy Advance) has no
    # filesystem path for the same domain and signals it instead via its own
    # `[parameters]` keys, listed here as a second alternative rather than
    # derived from the layout key name -- the two naming schemes don't always
    # match (`item_data`+`messages` vs `item_offset`, `moves` vs
    # `move_offset`), per the `gen3_frlg` engine's profile contract.
    "pokemon": (("personal",), ("personal_offset",)),
    "abilities": (("personal",), ("personal_offset",)),
    "moves": (("moves",), ("move_offset",)),
    "items": (("item_data", "messages"), ("item_offset",)),
    "encounters": (("encounters",), ("encounter_offset",)),
    "trainers": (("trainer_data", "trainer_parties"), ("trainer_offset",)),
    "locations": (
        ("map_matrices",),
        ("map_headers",),
        ("map_names",),
        ("gmapgroups_offset",),
    ),
}


def enabled_dataset_kinds(profile: GameProfile) -> tuple[str, ...]:
    """Return the complete dataset sections enabled for one profile."""
    supported, required = _engine_dataset_contract(profile)
    missing_required = [
        kind
        for kind in DATASET_KINDS
        if kind in required and not dataset_enabled(profile, kind)
    ]
    if missing_required:
        details = "; ".join(
            f"{kind} requires {_format_requirements(_SECTION_LAYOUT_REQUIREMENTS[kind])}"
            for kind in missing_required
        )
        raise ProfileError(
            f"Profile {profile.id!r} cannot build required dataset sections: {details}"
        )
    return tuple(
        kind
        for kind in DATASET_KINDS
        if kind in supported and (kind in required or dataset_enabled(profile, kind))
    )


def dataset_enabled(profile: GameProfile, kind: str) -> bool:
    try:
        alternatives = _SECTION_LAYOUT_REQUIREMENTS[kind]
    except KeyError as error:
        choices = ", ".join(DATASET_KINDS)
        raise ProfileError(
            f"Unknown dataset section {kind!r}; choose from {choices}"
        ) from error
    supported, _required = _engine_dataset_contract(profile)
    return kind in supported and any(
        _contains_all(profile, keys) for keys in alternatives
    )


def _engine_dataset_contract(
    profile: GameProfile,
) -> tuple[frozenset[str], frozenset[str]]:
    engine_id = getattr(profile, "engine", None)
    if not isinstance(engine_id, str):
        # Lightweight test doubles written before engine-owned section contracts
        # retain the current complete-engine policy.
        return frozenset(DATASET_KINDS), DEFAULT_REQUIRED_DATASET_KINDS
    engine = get_engine(engine_id)
    engine.profile_contract.validate(profile)
    return engine.dataset_kinds, engine.required_dataset_kinds


def describe_section_mismatch(
    enabled: Mapping[str, tuple[str, ...]],
) -> str:
    all_kinds = set().union(*enabled.values())
    differences = []
    for label, kinds in enabled.items():
        missing = sorted(all_kinds - set(kinds))
        if missing:
            differences.append(f"{label} omits {', '.join(missing)}")
    return "; ".join(differences)


def _contains_all(profile: GameProfile, keys: tuple[str, ...]) -> bool:
    return all(key in profile.layout or key in profile.parameters for key in keys)


def _format_requirements(alternatives: tuple[tuple[str, ...], ...]) -> str:
    return " or ".join(" + ".join(keys) for keys in alternatives)

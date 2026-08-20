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
    "pokemon": (("personal",),),
    "abilities": (("personal",),),
    "moves": (("moves",),),
    "items": (("item_data", "messages"),),
    "encounters": (("encounters",),),
    "trainers": (("trainer_data", "trainer_parties"),),
    "locations": (("map_matrices",), ("map_headers",), ("map_names",)),
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
    # NDS-style engines locate a domain via a `[layout]` archive path alias
    # (e.g. `personal = "a/0/0/2"`); a flat, offset-addressed platform (e.g.
    # Game Boy Advance) has no filesystem path for the same domain and
    # signals it instead via a `<key>_offset` parameter (e.g.
    # `personal_offset`), per the `gen3_frlg` engine's profile contract.
    # Either signal counts as "this profile configures this domain."
    return all(
        key in profile.layout or f"{key}_offset" in profile.parameters for key in keys
    )


def _format_requirements(alternatives: tuple[tuple[str, ...], ...]) -> str:
    return " or ".join(" + ".join(keys) for keys in alternatives)

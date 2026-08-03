from __future__ import annotations

from collections.abc import Mapping

from romwiki.profiles.models import GameProfile
from romwiki.util.errors import ProfileError

DATASET_KINDS = (
    "pokemon",
    "abilities",
    "moves",
    "items",
    "encounters",
    "trainers",
    "locations",
)

REQUIRED_DATASET_KINDS = frozenset({"pokemon", "moves", "items", "encounters"})

_SECTION_LAYOUT_REQUIREMENTS: dict[str, tuple[tuple[str, ...], ...]] = {
    "pokemon": (("personal",),),
    "abilities": (("messages",),),
    "moves": (("moves",),),
    "items": (("item_data", "messages"),),
    "encounters": (("encounters",),),
    "trainers": (("trainer_data", "trainer_parties"),),
    "locations": (("map_matrices",), ("map_headers",)),
}


def enabled_dataset_kinds(profile: GameProfile) -> tuple[str, ...]:
    """Return the complete dataset sections enabled for one profile."""
    missing_required = [
        kind
        for kind in DATASET_KINDS
        if kind in REQUIRED_DATASET_KINDS and not dataset_enabled(profile, kind)
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
        if kind in REQUIRED_DATASET_KINDS or dataset_enabled(profile, kind)
    )


def dataset_enabled(profile: GameProfile, kind: str) -> bool:
    try:
        alternatives = _SECTION_LAYOUT_REQUIREMENTS[kind]
    except KeyError as error:
        choices = ", ".join(DATASET_KINDS)
        raise ProfileError(
            f"Unknown dataset section {kind!r}; choose from {choices}"
        ) from error
    return any(_contains_all(profile.layout, keys) for keys in alternatives)


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


def _contains_all(layout: Mapping[str, str], keys: tuple[str, ...]) -> bool:
    return all(key in layout for key in keys)


def _format_requirements(alternatives: tuple[tuple[str, ...], ...]) -> str:
    return " or ".join(" + ".join(keys) for keys in alternatives)

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from romwiki.util.errors import DataSourceError
from romwiki.util.text import name_slug, normalize_display_name


def reference_name_table(dataset: Mapping[str, Any], field: str) -> list[str] | None:
    """Return a ROM-derived name table that extraction sized for this build."""
    names = dataset.get(field)
    if names is None:
        return None
    if (
        not isinstance(names, list)
        or not names
        or any(not isinstance(name, str) or not name for name in names)
    ):
        raise DataSourceError(f"Invalid ROM-derived {field.replace('_', ' ')}")
    return names


def resolve_type_names(
    dataset: Mapping[str, Any],
    fallback: Mapping[int, str] | None,
) -> dict[int, str]:
    result = dict(fallback or {})
    names = reference_name_table(dataset, "type_names")
    if names is not None:
        result.update((type_id, name_slug(name)) for type_id, name in enumerate(names))
    return result


def resolve_move_names(
    dataset: Mapping[str, Any],
    fallback: Mapping[int, str] | None,
) -> dict[int, str]:
    result = dict(fallback or {})
    names = reference_name_table(dataset, "move_names")
    if names is not None:
        result.update((move_id, name_slug(name)) for move_id, name in enumerate(names))
    return result


def resolve_ability_names(dataset: Mapping[str, Any]) -> list[str] | None:
    return reference_name_table(dataset, "ability_names")


def resolve_pokemon_names(dataset: Mapping[str, Any]) -> list[str] | None:
    names = reference_name_table(dataset, "pokemon_names")
    if names is None:
        return None
    return [normalize_display_name(name) for name in names]


def resolve_item_names(dataset: Mapping[str, Any]) -> list[str] | None:
    return reference_name_table(dataset, "item_names")

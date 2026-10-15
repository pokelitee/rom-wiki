from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from romwiki.engines.concerns import EnrichmentTables
from romwiki.util.errors import DataSourceError
from romwiki.util.text import name_slug, normalize_display_name


def reference_name_table(
    dataset: Mapping[str, Any], field: str, expected_count: int
) -> list[str] | None:
    names = dataset.get(field)
    if names is None:
        return None
    if (
        not isinstance(names, list)
        or len(names) != expected_count
        or any(not isinstance(name, str) or not name for name in names)
    ):
        raise DataSourceError(
            f"Expected exactly {expected_count} ROM-derived {field.replace('_', ' ')}"
        )
    return names


def resolve_type_names(
    engine: EnrichmentTables,
    dataset: Mapping[str, Any],
    fallback: Mapping[int, str] | None,
) -> dict[int, str]:
    result = dict(fallback or {})
    names = reference_name_table(dataset, "type_names", engine.TYPE_NAME_COUNT)
    if names is not None:
        result.update((type_id, name_slug(name)) for type_id, name in enumerate(names))
    return result


def resolve_move_names(
    engine: EnrichmentTables,
    dataset: Mapping[str, Any],
    fallback: Mapping[int, str] | None,
) -> dict[int, str]:
    result = dict(fallback or {})
    names = reference_name_table(dataset, "move_names", engine.MOVE_NAME_COUNT)
    if names is not None:
        result.update((move_id, name_slug(name)) for move_id, name in enumerate(names))
    return result


def resolve_ability_names(
    engine: EnrichmentTables, dataset: Mapping[str, Any]
) -> list[str] | None:
    return reference_name_table(dataset, "ability_names", engine.ABILITY_NAME_COUNT)


def resolve_pokemon_names(
    engine: EnrichmentTables, dataset: Mapping[str, Any]
) -> list[str] | None:
    names = reference_name_table(dataset, "pokemon_names", engine.POKEMON_NAME_COUNT)
    if names is None:
        return None
    return [normalize_display_name(name) for name in names]


def resolve_item_names(
    engine: EnrichmentTables, dataset: Mapping[str, Any]
) -> list[str] | None:
    return reference_name_table(dataset, "item_names", engine.ITEM_NAME_COUNT)

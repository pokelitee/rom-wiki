"""Helpers shared by every relationship domain (wild encounters, trainers,
acquisition, move learners, location encounters)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from romwiki.pipeline.semantics.location_sections import location_reference_label
from romwiki.util.errors import DataSourceError


def _validate_datasets(datasets: Mapping[str, Mapping[str, Any]]) -> None:
    games = {
        str(dataset["game"])
        for dataset in datasets.values()
        if dataset is not None
        and dataset.get("records") is not None
        and dataset.get("game") is not None
    }
    if len(games) > 1:
        raise DataSourceError("Relationship datasets must be for the same game")


def _records(
    datasets: Mapping[str, Mapping[str, Any]], kind: str
) -> list[dict[str, Any]]:

    dataset = datasets.get(kind)
    if dataset is None:
        return []
    records = dataset.get("records")
    if not isinstance(records, list):
        raise DataSourceError(f"{kind} dataset records must be a list")
    return records


def _pokemon_aliases(
    records: list[dict[str, Any]],
) -> dict[int | str, str]:
    aliases: dict[int | str, str] = {}
    ambiguous: set[int | str] = set()
    for record in records:
        if not record.get("public", True):
            continue
        slug = record.get("slug")
        if not isinstance(slug, str):
            continue
        for alias in (
            slug,
            record.get("member"),
            record.get("national_dex_id"),
        ):
            if alias is None or alias in ambiguous:
                continue
            existing = aliases.get(alias)
            if existing is not None and existing != slug:
                aliases.pop(alias)
                ambiguous.add(alias)
            else:
                aliases[alias] = slug
    return aliases


def _pokemon_slug(
    value: Mapping[str, Any] | None,
    species_id: int | None,
    aliases: Mapping[int | str, str],
) -> str | None:
    if value is not None:
        slug = value.get("slug")
        if isinstance(slug, str) and slug in aliases:
            return aliases[slug]
    return aliases.get(species_id) if species_id is not None else None


def _record_versions(record: Mapping[str, Any]) -> tuple[str, ...]:
    versions = record.get("versions")
    if isinstance(versions, list) and all(isinstance(value, str) for value in versions):
        return tuple(versions)
    return ()


def _record_variants(
    record: dict[str, Any],
) -> Iterable[tuple[tuple[str, ...], dict[str, Any]]]:
    variants = record.get("version_variants")
    if isinstance(variants, dict):
        for version, variant in variants.items():
            if isinstance(version, str) and isinstance(variant, dict):
                yield (version,), variant
        return
    yield _record_versions(record), record


def _freeze(
    values: Mapping[Any, list[Any]],
    sort_key: Any,
) -> dict[Any, tuple[Any, ...]]:
    return {
        key: tuple(_deduplicate(sorted(entries, key=sort_key)))
        for key, entries in sorted(values.items(), key=lambda item: item[0])
    }


def _deduplicate(values: Iterable[Any]) -> Iterable[Any]:
    seen = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        yield value


def _location_display_name(location: Mapping[str, Any]) -> str:
    return location_reference_label(location)

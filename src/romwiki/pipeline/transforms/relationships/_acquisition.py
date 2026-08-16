"""Acquisition relationships: how a Pokemon can be obtained (gift, static,
trade, honey tree, fossil revival, egg, ...)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ._shared import _location_display_name, _pokemon_slug, _record_versions


@dataclass(frozen=True, slots=True)
class AcquisitionReference:
    pokemon_slug: str
    kind: str
    location_id: int | None
    location_name: str | None
    level: int | None
    detail: str | None
    source_item_id: int | None
    source_item_slug: str | None
    versions: tuple[str, ...]


def _acquisition_references(
    pokemon_records: list[dict[str, Any]],
    location_records: list[dict[str, Any]],
    item_records: list[dict[str, Any]],
    trade_records: list[dict[str, Any]],
    aliases: Mapping[int | str, str],
) -> dict[str, list[AcquisitionReference]]:
    result: dict[str, list[AcquisitionReference]] = defaultdict(list)
    for location in location_records:
        versions = _record_versions(location)
        common = {
            "location_id": location["header_id"],
            "location_name": _location_display_name(location),
            "versions": versions,
        }
        for gift in location.get("pokemon_gifts", []):
            gift_kind = "egg" if gift.get("kind") == "egg" else "gift"
            _add_acquisition(result, aliases, gift, gift_kind, common)
        for encounter in location.get("static_encounters", []):
            _add_acquisition(result, aliases, encounter, "static", common)
        for trade in location.get("npc_trades", []):
            offered = {
                "species_id": trade.get("offered_species_id"),
                "level": None,
                "detail": f"Trade for {trade.get('requested_species_name', 'Pokémon')}",
            }
            _add_acquisition(
                result,
                aliases,
                offered,
                "trade",
                {
                    **common,
                    "versions": tuple(trade.get("versions", versions)),
                },
            )
        honey_tree = location.get("honey_tree")
        if isinstance(honey_tree, dict):
            for rarity in ("common", "uncommon", "rare"):
                for pokemon in honey_tree.get(rarity, []):
                    _add_acquisition(
                        result,
                        aliases,
                        pokemon,
                        "honey-tree",
                        {**common, "detail": rarity},
                    )
        daily = location.get("daily_encounter_pool")
        if isinstance(daily, dict):
            for pokemon in daily.get("species", []):
                _add_acquisition(
                    result,
                    aliases,
                    pokemon,
                    daily["kind"],
                    common,
                )
            for pokemon in daily.get("pre_national_dex_species") or []:
                _add_acquisition(
                    result,
                    aliases,
                    pokemon,
                    daily["kind"],
                    {**common, "detail": "before National Pokédex"},
                )

    for item in item_records:
        pokemon = item.get("revives_into")
        if isinstance(pokemon, dict):
            locations = item.get("revives_at") or [None]
            for location in locations:
                _add_acquisition(
                    result,
                    aliases,
                    pokemon,
                    "fossil-revival",
                    {
                        "location_id": (
                            location.get("header_id") if location else None
                        ),
                        "location_name": location.get("name") if location else None,
                        "detail": item.get("name"),
                        "source_item_id": item.get("item_id"),
                        "source_item_slug": item.get("slug"),
                        "versions": _record_versions(item),
                    },
                )

    for trade in trade_records:
        offered = trade.get("offered_pokemon")
        requested = trade.get("requested_pokemon") or {}
        if not isinstance(offered, dict):
            continue
        if trade.get("locations"):
            # Fixed trades were already emitted from the location records,
            # which preserve nested sibling-version ownership precisely.
            continue
        _add_acquisition(
            result,
            aliases,
            {
                "pokemon": offered,
                "species_id": offered.get("species_id"),
                "detail": _detached_trade_detail(trade, requested),
            },
            "trade",
            {
                "location_id": None,
                "location_name": None,
                "versions": _record_versions(trade),
            },
        )

    # Preserve static encounters that have no resolved location record.
    for pokemon in pokemon_records:
        slug = pokemon.get("slug")
        if not isinstance(slug, str):
            continue
        versions = _record_versions(pokemon)
        for encounter in pokemon.get("static_encounters", []):
            location = encounter.get("location") or {}
            result[slug].append(
                AcquisitionReference(
                    pokemon_slug=slug,
                    kind="egg" if encounter.get("is_egg") else "static",
                    location_id=location.get("header_id"),
                    location_name=location.get("name"),
                    level=None if encounter.get("is_egg") else encounter.get("level"),
                    detail=encounter.get("command"),
                    source_item_id=None,
                    source_item_slug=None,
                    versions=versions,
                )
            )
    return result


def _detached_trade_detail(trade: dict[str, Any], requested: dict[str, Any]) -> str:
    requested_name = requested.get("name")
    if trade.get("interaction") == "xtransceiver":
        ot_name = trade.get("ot_name")
        label = (
            f"Xtransceiver trade with {ot_name}" if ot_name else "Xtransceiver trade"
        )
    else:
        label = "Trade"
    return f"{label} for {requested_name}" if requested_name else label


def _add_acquisition(
    result: dict[str, list[AcquisitionReference]],
    aliases: Mapping[int | str, str],
    value: Mapping[str, Any],
    kind: str,
    common: Mapping[str, Any],
) -> None:
    slug = _pokemon_slug(
        value.get("pokemon") if isinstance(value.get("pokemon"), Mapping) else value,
        value.get("species_id"),
        aliases,
    )
    if slug is None:
        return
    result[slug].append(
        AcquisitionReference(
            pokemon_slug=slug,
            kind=kind,
            location_id=common.get("location_id"),
            location_name=common.get("location_name"),
            level=value.get("level"),
            detail=value.get(
                "detail",
                value.get("command", common.get("detail")),
            ),
            source_item_id=common.get("source_item_id"),
            source_item_slug=common.get("source_item_slug"),
            versions=tuple(common.get("versions", ())),
        )
    )


def _acquisition_sort_key(value: AcquisitionReference) -> tuple[Any, ...]:
    return (
        value.kind,
        value.location_name or "",
        value.location_id if value.location_id is not None else -1,
        value.level if value.level is not None else -1,
        value.detail or "",
        value.source_item_id if value.source_item_id is not None else -1,
        value.versions,
    )

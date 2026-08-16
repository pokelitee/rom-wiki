from __future__ import annotations

from typing import Any

from romwiki.engines.registry import get_engine
from romwiki.util.errors import DataSourceError


def enrich_npc_trade_dataset(
    dataset: dict[str, Any],
    pokemon_dataset: dict[str, Any],
    location_dataset: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve detached trade species to the game's public Pokémon records."""
    if dataset.get("game") != pokemon_dataset.get("game"):
        raise DataSourceError("Trade and Pokémon datasets must be for the same game")
    engine = get_engine(str(dataset["engine"])).enrich
    pokemon_by_species = {
        record["national_dex_id"]: record
        for record in pokemon_dataset.get("records", [])
        if record.get("public") and record.get("form") is None
    }
    pokemon_by_slug = {
        record["slug"]: record
        for record in pokemon_dataset.get("records", [])
        if record.get("public") and isinstance(record.get("slug"), str)
    }
    records = []
    locations_by_trade: dict[int, list[dict[str, Any]]] = {}
    for location in (location_dataset or {}).get("records", []):
        for trade in location.get("npc_trades", []):
            locations_by_trade.setdefault(trade["trade_id"], []).append(
                {"header_id": location["header_id"], "name": location["name"]}
            )
    for record in dataset.get("records", []):
        offered = None
        form_id = record.get("offered_forme_id", 0)
        if form_id:
            form_slug = engine.TRAINER_FORM_SLUGS.get(
                (record["offered_species_id"], form_id)
            )
            if form_slug is not None:
                offered = pokemon_by_slug.get(form_slug)
        if offered is None:
            offered = pokemon_by_species.get(record["offered_species_id"])
        requested = pokemon_by_species.get(record["requested_species_id"])
        records.append(
            {
                **record,
                "offered_pokemon": _pokemon_reference(
                    offered, record["offered_species_id"]
                ),
                "requested_pokemon": _pokemon_reference(
                    requested, record["requested_species_id"]
                ),
                "locations": locations_by_trade.get(record["trade_id"], []),
            }
        )
    return {**dataset, "records": records}


def _pokemon_reference(
    record: dict[str, Any] | None,
    species_id: int,
) -> dict[str, Any]:
    if record is None:
        return {"species_id": species_id, "name": None, "slug": None}
    return {
        "species_id": species_id,
        "member": record["member"],
        "name": record["name"],
        "slug": record["slug"],
    }

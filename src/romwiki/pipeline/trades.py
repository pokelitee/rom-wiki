from __future__ import annotations

from typing import Any

from romwiki.engines.registry import get_engine
from romwiki.pipeline.identify import InspectionResult
from romwiki.platforms.registry import get_platform
from romwiki.schema.versions import NPC_TRADES_RAW_SCHEMA_VERSION
from romwiki.util.errors import DataSourceError, InvalidRomError, ProfileError


def extract_npc_trade_dataset(result: InspectionResult) -> dict[str, Any]:
    if result.match is None:
        raise ProfileError("A known game profile is required for trade extraction")
    profile = result.match.profile
    try:
        trades_path = profile.layout["npc_trades"]
        messages_path = profile.layout["messages"]
        trade_names_member = profile.parameters["npc_trade_names_member"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} is missing NPC trade metadata: {error.args[0]}"
        ) from error
    unused_trade_ids = frozenset(profile.parameters.get("npc_trades_unused", ()))

    platform = get_platform(profile.platform)
    engine = get_engine(profile.engine).trades
    interaction_by_id = getattr(engine, "NPC_TRADE_INTERACTION_BY_ID", {})
    filesystem = platform.filesystem_from_image(result.image)
    trades = platform.archive_cls.from_bytes(filesystem.read(trades_path))
    messages = platform.archive_cls.from_bytes(
        filesystem.read(messages_path),
        allow_truncated=profile.parameters.get("messages_allow_truncated", False),
    )
    trade_strings = engine.parse_english_message_archive(
        messages.read(trade_names_member)
    )
    if len(trade_strings) != len(trades.members) * 2:
        raise InvalidRomError(
            "NPC trade name bank must contain one nickname and OT name per trade"
        )

    records = []
    for member in trades.members:
        if member.index in unused_trade_ids:
            continue
        record = engine.parse_npc_trade_record(
            trades.read(member.index),
            trade_id=member.index,
            nickname=trade_strings[member.index * 2],
            ot_name=trade_strings[member.index * 2 + 1],
            archive_path=trades_path,
        ).to_dict()
        record["interaction"] = interaction_by_id.get(
            member.index, record["interaction"]
        )
        records.append(record)
    return {
        "schema_version": NPC_TRADES_RAW_SCHEMA_VERSION,
        "game": profile.id,
        "engine": profile.engine,
        "dataset": "trades",
        "record_count": len(records),
        "source": {
            "rom_sha256": result.image.hashes.sha256,
            "archive": trades_path,
            "trade_names": {"archive": messages_path, "member": trade_names_member},
        },
        "records": records,
    }
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

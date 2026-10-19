from __future__ import annotations

from dataclasses import replace
from typing import Any

from romwiki.engines.registry import get_engine
from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.pipeline.extraction.locations.gba_map_events import (
    GbaMapNames,
    extract_gba_map_facts,
)
from romwiki.pipeline.extraction.locations.helpers import extract_trainer_references
from romwiki.pipeline.extraction.map_headers import (
    iter_gba_map_headers,
    read_region_names,
)
from romwiki.platforms.registry import get_platform
from romwiki.schema.datasets import dataset_envelope
from romwiki.schema.versions import LOCATIONS_RAW_SCHEMA_VERSION
from romwiki.util.errors import InvalidRomError, ProfileError


def extract_gba_map_groups_location_dataset(
    result: InspectionResult,
    trainer_dataset: dict[str, Any] | None = None,
    item_dataset: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One location per Generation III map, in `gMapGroups` order."""
    assert result.match is not None
    profile = result.match.profile
    platform = get_platform(profile.platform)
    if platform.read_bytes is None:
        raise ProfileError(f"Platform {profile.platform!r} does not support flat reads")
    read_bytes = platform.read_bytes
    engine = get_engine(profile.engine).locations
    headers = list(iter_gba_map_headers(engine, platform, result.image, profile))
    gmapgroups_offset = profile.int_parameter("gmapgroups_offset")
    region_name_offset = profile.int_parameter("region_name_offset")

    # Disassembly makes many small reads, so read the ROM once.
    rom = read_bytes(result.image, 0, result.image.size)

    def read(offset: int, size: int) -> bytes:
        if offset < 0 or offset + size > len(rom):
            raise InvalidRomError(
                f"Read of {size} byte(s) at {offset:#x} is past the ROM"
            )
        return rom[offset : offset + size]

    facts, undecoded_scripts = extract_gba_map_facts(
        engine, read, headers, _names(engine, read, profile, item_dataset)
    )
    trainers = extract_trainer_references(result, trainer_dataset)
    records = [
        replace(
            record,
            trainers=tuple(trainers.get(record.header_id, ())),
            warps=tuple(facts[record.header_id].warps),
            connections=tuple(facts[record.header_id].connections),
            items=tuple(facts[record.header_id].items),
            script_awarded_items=tuple(facts[record.header_id].script_awarded_items),
            static_encounters=tuple(facts[record.header_id].static_encounters),
            pokemon_gifts=tuple(facts[record.header_id].pokemon_gifts),
            shops=tuple(facts[record.header_id].shops),
            npc_trades=tuple(facts[record.header_id].npc_trades),
        ).to_dict()
        for record in engine.parse_map_header_table(
            b"".join(header.data for header in headers),
            read_region_names(engine, platform, result.image, profile),
            header_ids=[header.header_id for header in headers],
            archive_path=f"gMapGroups:{gmapgroups_offset:#x}",
        )
    ]
    envelope = dataset_envelope(
        schema_version=LOCATIONS_RAW_SCHEMA_VERSION,
        game=profile.id,
        engine=profile.engine,
        dataset="locations",
        source={
            "gmapgroups_offset": gmapgroups_offset,
            "region_name_offset": region_name_offset,
        },
        records=records,
    )
    for field, count_key in (
        ("trainers", "trainer_reference_count"),
        ("warps", "warp_reference_count"),
        ("connections", "connection_reference_count"),
        ("items", "item_reference_count"),
        ("script_awarded_items", "script_awarded_item_reference_count"),
        ("static_encounters", "static_encounter_reference_count"),
        ("pokemon_gifts", "pokemon_gift_reference_count"),
        ("shops", "shop_reference_count"),
        ("npc_trades", "npc_trade_reference_count"),
    ):
        envelope[count_key] = sum(len(record[field]) for record in records)
    envelope["undecoded_object_script_count"] = undecoded_scripts
    return envelope


def _names(
    engine: Any,
    read: Any,
    profile: Any,
    item_dataset: dict[str, Any] | None,
) -> GbaMapNames:
    stride = profile.int_parameter("pokemon_name_stride")
    count = profile.int_parameter("personal_count")
    species = engine.decode_gen3_name_table(
        read(profile.int_parameter("pokemon_name_offset"), stride * count),
        stride=stride,
        count=count,
    )
    items = (item_dataset or {}).get("records", [])
    trades: list[Any] = []
    if "trade_table_offset" in profile.parameters:
        size = engine.INGAME_TRADE_SIZE
        data = read(
            profile.int_parameter("trade_table_offset"),
            size * profile.int_parameter("trade_count"),
        )
        trades = [
            engine.parse_ingame_trade(data[start : start + size])
            for start in range(0, len(data), size)
        ]
    return GbaMapNames(
        species=species,
        items={item["item_id"]: item["name"] for item in items},
        item_prices={item["item_id"]: item["price"] for item in items},
        trades=trades,
    )

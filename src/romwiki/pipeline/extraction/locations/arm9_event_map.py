from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from romwiki.engines.concerns import LocationConcern
from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.pipeline.extraction.locations.arm9_event_map_source import (
    EventMapFeatures,
    EventMapLoadedSource,
    EventMapNames,
    load_event_map_source,
)
from romwiki.pipeline.extraction.locations.event_map_shops import (
    EventMapShopCatalogs,
    extract_event_map_location_shops,
)
from romwiki.pipeline.extraction.locations.helpers import (
    EventMapItemScan,
    extract_event_map_connections,
    extract_event_map_items,
    extract_trainer_references,
)
from romwiki.pipeline.semantics.location_sections import (
    resolve_location_section,
)
from romwiki.schema import (
    EventMapLocation,
    LocationItem,
    LocationNpcTrade,
    LocationPokemonGift,
    LocationRoamingActivation,
    LocationScriptAwardedItem,
    LocationShop,
    LocationStaticEncounter,
    LocationWarp,
    RecordProvenance,
)
from romwiki.schema.versions import LOCATIONS_RAW_SCHEMA_VERSION
from romwiki.util.errors import InvalidRomError, ProfileError


@dataclass(frozen=True)
class _EventMapRecordContext:
    profile: Any
    engine: Any
    headers: tuple[Any, ...]
    scripts: Any
    names: EventMapNames
    shops: EventMapShopCatalogs
    features: EventMapFeatures
    npc_trade_records: tuple[Any, ...]
    roaming_by_script: dict[int, tuple[LocationRoamingActivation, ...]]
    raw_warps_by_header: dict[int, tuple[Any, ...]]
    raw_items_by_header: dict[int, tuple[LocationItem, ...]]
    connections: dict[int, list[Any]]
    trainers: dict[int, list[Any]]
    static_encounter_location_metadata: list[dict[str, int]]


@dataclass(frozen=True)
class _EventMapRelationships:
    items_by_event: dict[int, EventMapItemScan]
    raw_warps_by_header: dict[int, tuple[Any, ...]]
    raw_items_by_header: dict[int, tuple[LocationItem, ...]]
    connections: dict[int, list[Any]]
    trainers: dict[int, list[Any]]


@dataclass(frozen=True)
class _EventMapScriptSections:
    shops: tuple[LocationShop, ...]
    gifts: tuple[LocationPokemonGift, ...]
    npc_trades: tuple[LocationNpcTrade, ...]
    script_awarded_items: tuple[LocationScriptAwardedItem, ...]


def extract_arm9_event_map_location_dataset(
    result: InspectionResult,
    trainer_dataset: dict[str, Any] | None = None,
    static_encounter_dataset: dict[str, Any] | None = None,
    item_dataset: dict[str, Any] | None = None,
    mart_dataset: dict[str, Any] | None = None,
    trade_dataset: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source = load_event_map_source(result)
    relationships = _collect_event_map_relationships(result, source, trainer_dataset)
    records = _build_event_map_location_records(
        _EventMapRecordContext(
            profile=source.profile,
            engine=source.engine,
            headers=source.headers,
            scripts=source.scripts,
            names=source.names,
            shops=source.shops,
            features=source.features,
            npc_trade_records=source.npc_trade_records,
            roaming_by_script=source.roaming_by_script,
            raw_warps_by_header=relationships.raw_warps_by_header,
            raw_items_by_header=relationships.raw_items_by_header,
            connections=relationships.connections,
            trainers=relationships.trainers,
            static_encounter_location_metadata=(
                source.static_encounter_location_metadata
            ),
        )
    )
    return _build_event_map_location_envelope(source, relationships, records)


def _collect_event_map_relationships(
    result: InspectionResult,
    source: EventMapLoadedSource,
    trainer_dataset: dict[str, Any] | None,
) -> _EventMapRelationships:
    events = source.platform.archive_cls.from_bytes(
        source.filesystem.read(source.events_path)
    )
    matrices = source.platform.archive_cls.from_bytes(
        source.filesystem.read(source.matrices_path)
    )
    events_by_id: dict[int, Any] = {}
    items_by_event: dict[int, EventMapItemScan] = {}
    raw_warps_by_header: dict[int, tuple[Any, ...]] = {}
    raw_items_by_header: dict[int, tuple[LocationItem, ...]] = {}
    for header in source.headers:
        if header.event_file_id == source.features.null_event_id:
            raw_warps_by_header[header.header_id] = ()
            raw_items_by_header[header.header_id] = ()
            continue
        if header.event_file_id >= len(events.members):
            raise InvalidRomError(
                f"Map header {header.header_id} references missing event file "
                f"{header.event_file_id}"
            )
        if header.event_file_id not in events_by_id:
            events_by_id[header.event_file_id] = source.engine.parse_map_events(
                events.read(header.event_file_id),
                event_file_id=header.event_file_id,
            )
            items_by_event[header.event_file_id] = extract_event_map_items(
                source.engine,
                events_by_id[header.event_file_id],
                source.names.item,
            )
        raw_warps_by_header[header.header_id] = events_by_id[header.event_file_id].warps
        raw_items_by_header[header.header_id] = items_by_event[
            header.event_file_id
        ].items
    return _EventMapRelationships(
        items_by_event=items_by_event,
        raw_warps_by_header=raw_warps_by_header,
        raw_items_by_header=raw_items_by_header,
        connections=extract_event_map_connections(
            source.engine,
            source.headers,
            matrices,
            source.names.location,
            source.matrix_void_header_ids,
        ),
        trainers=extract_trainer_references(result, trainer_dataset),
    )


def _build_event_map_location_envelope(
    source: EventMapLoadedSource,
    relationships: _EventMapRelationships,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": LOCATIONS_RAW_SCHEMA_VERSION,
        "game": source.profile.id,
        "engine": source.profile.engine,
        "dataset": "locations",
        "record_count": len(records),
        "warp_count": sum(len(record["warps"]) for record in records),
        "dynamic_warp_count": sum(
            warp["dynamic"] for record in records for warp in record["warps"]
        ),
        "missing_destination_warp_count": sum(
            warp["destination_warp_exists"] is False
            for record in records
            for warp in record["warps"]
        ),
        "connection_count": sum(len(record["connections"]) for record in records),
        "visible_item_count": sum(
            item.kind == "visible"
            for scan in relationships.items_by_event.values()
            for item in scan.items
        ),
        "hidden_item_count": sum(
            item.kind == "hidden"
            for scan in relationships.items_by_event.values()
            for item in scan.items
        ),
        "unresolved_visible_item_count": sum(
            scan.unresolved_visible_count
            for scan in relationships.items_by_event.values()
        ),
        "unresolved_hidden_item_count": sum(
            scan.unresolved_hidden_count
            for scan in relationships.items_by_event.values()
        ),
        "location_item_reference_count": sum(
            len(record["items"]) for record in records
        ),
        "script_awarded_item_reference_count": sum(
            len(record["script_awarded_items"]) for record in records
        ),
        "shop_count": sum(len(record["shops"]) for record in records),
        "shop_item_reference_count": sum(
            len(shop["items"]) for record in records for shop in record["shops"]
        ),
        "pokemon_gift_count": sum(len(record["pokemon_gifts"]) for record in records),
        "npc_trade_count": sum(len(record["npc_trades"]) for record in records),
        "static_encounter_count": sum(
            len(record["static_encounters"]) for record in records
        ),
        "roaming_activation_count": source.roaming_activation_count,
        "source": source.source_metadata,
        "records": records,
    }


def _build_event_map_location_records(
    context: _EventMapRecordContext,
) -> list[dict[str, Any]]:
    sections_by_script: dict[int, _EventMapScriptSections] = {}
    static_encounters_by_location: dict[
        tuple[int, int], tuple[LocationStaticEncounter, ...]
    ] = {}
    header_ids_by_script: dict[int, list[int]] = defaultdict(list)
    for header in context.headers:
        header_ids_by_script[header.script_file_id].append(header.header_id)
    static_encounter_header_by_command = _static_encounter_header_by_command(
        context.static_encounter_location_metadata
    )

    records = []
    for header in context.headers:
        section_name, section_name_source = resolve_location_section(
            context.profile,
            header_id=header.header_id,
            internal_name=header.internal_name,
        )
        if header.script_file_id >= len(context.scripts.members):
            raise InvalidRomError(
                f"Map header {header.header_id} references missing script file "
                f"{header.script_file_id}"
            )
        script = context.scripts.read(header.script_file_id)
        if header.script_file_id not in sections_by_script:
            sections_by_script[header.script_file_id] = (
                _extract_event_map_script_sections(
                    context, script, script_file_id=header.script_file_id
                )
            )
        static_key = (header.script_file_id, header.header_id)
        if static_key not in static_encounters_by_location:
            static_encounters_by_location[static_key] = (
                _extract_event_map_location_static_encounters(
                    context.engine,
                    script,
                    script_file_id=header.script_file_id,
                    map_header_id=header.header_id,
                    script_is_shared=(
                        len(header_ids_by_script[header.script_file_id]) > 1
                    ),
                    explicit_header_by_command=static_encounter_header_by_command,
                    pokemon_names=context.names.pokemon,
                )
            )
        records.append(
            _build_event_map_location_record(
                context,
                header,
                _build_event_map_location_warps(context, header),
                sections=sections_by_script[header.script_file_id],
                static_encounters=static_encounters_by_location[static_key],
                section_name=section_name,
                section_name_source=section_name_source,
            )
        )
    return records


def _static_encounter_header_by_command(
    static_encounter_location_metadata: list[dict[str, int]],
) -> dict[tuple[int, int], int]:
    header_by_command = {
        (metadata["script_member"], metadata["command_offset"]): metadata[
            "map_header_id"
        ]
        for metadata in static_encounter_location_metadata
    }
    if len(header_by_command) != len(static_encounter_location_metadata):
        raise ProfileError("Static encounter location metadata contains duplicates")
    return header_by_command


def _extract_event_map_script_sections(
    context: _EventMapRecordContext, script: bytes, *, script_file_id: int
) -> _EventMapScriptSections:
    return _EventMapScriptSections(
        shops=extract_event_map_location_shops(
            context.engine,
            script,
            script_file_id=script_file_id,
            catalogs=context.shops,
        ),
        gifts=_extract_event_map_location_pokemon_gifts(
            context.engine,
            script,
            script_file_id=script_file_id,
            pokemon_names=context.names.pokemon,
            item_names=context.names.item,
        ),
        npc_trades=_extract_event_map_location_npc_trades(
            context.engine,
            script,
            script_file_id=script_file_id,
            trade_records=context.npc_trade_records,
            trade_names=context.names.npc_trade,
            pokemon_names=context.names.pokemon,
            item_names=context.names.item,
        ),
        script_awarded_items=_extract_event_map_location_script_awarded_items(
            context.engine,
            script,
            script_file_id=script_file_id,
            item_names=context.names.item,
        ),
    )


def _build_event_map_location_warps(
    context: _EventMapRecordContext, header: Any
) -> list[LocationWarp]:
    warps = []
    for warp in context.raw_warps_by_header[header.header_id]:
        dynamic = (
            warp.destination_header_id == context.features.dynamic_warp_header_id
            and warp.destination_warp_id == context.features.dynamic_warp_id
        )
        if dynamic:
            warps.append(
                LocationWarp(
                    index=warp.index,
                    x=warp.x,
                    z=warp.z,
                    destination_header_id=None,
                    destination_warp_id=None,
                    destination_name=None,
                    destination_section_name=None,
                    destination_internal_name=None,
                    destination_warp_exists=None,
                    dynamic=True,
                )
            )
            continue
        if not 0 <= warp.destination_header_id < len(context.headers):
            raise InvalidRomError(
                f"Map header {header.header_id} warp {warp.index} references "
                f"missing header {warp.destination_header_id}"
            )
        destination = context.headers[warp.destination_header_id]
        destination_warps = context.raw_warps_by_header[destination.header_id]
        destination_section_name, _ = resolve_location_section(
            context.profile,
            header_id=destination.header_id,
            internal_name=destination.internal_name,
        )
        warps.append(
            LocationWarp(
                index=warp.index,
                x=warp.x,
                z=warp.z,
                destination_header_id=destination.header_id,
                destination_warp_id=warp.destination_warp_id,
                destination_name=context.names.location[destination.location_name_id],
                destination_section_name=destination_section_name,
                destination_internal_name=destination.internal_name,
                destination_warp_exists=(
                    warp.destination_warp_id < len(destination_warps)
                ),
                dynamic=False,
            )
        )
    return warps


def _build_event_map_location_record(
    context: _EventMapRecordContext,
    header: Any,
    warps: list[LocationWarp],
    *,
    sections: _EventMapScriptSections,
    static_encounters: tuple[LocationStaticEncounter, ...],
    section_name: str | None,
    section_name_source: dict[str, str] | None,
) -> dict[str, Any]:
    features = context.features
    return EventMapLocation(
        header_id=header.header_id,
        internal_name=header.internal_name,
        location_name_id=header.location_name_id,
        name=context.names.location[header.location_name_id],
        matrix_id=header.matrix_id,
        area_data_id=header.area_data_id,
        level_script_id=header.level_script_id,
        text_archive_id=header.text_archive_id,
        day_music_id=header.day_music_id,
        night_music_id=header.night_music_id,
        weather_id=header.weather_id,
        camera_id=header.camera_id,
        map_flags=header.flags,
        event_file_id=(
            None
            if header.event_file_id == features.null_event_id
            else header.event_file_id
        ),
        encounter_id=(
            None
            if header.encounter_id == features.null_encounter_id
            else header.encounter_id
        ),
        warps=tuple(warps),
        connections=tuple(context.connections.get(header.header_id, ())),
        trainers=tuple(context.trainers.get(header.header_id, ())),
        items=context.raw_items_by_header[header.header_id],
        shops=sections.shops,
        pokemon_gifts=sections.gifts,
        static_encounters=static_encounters,
        roaming_activations=context.roaming_by_script[header.script_file_id],
        npc_trades=sections.npc_trades,
        script_awarded_items=sections.script_awarded_items,
        honey_tree=(
            features.honey_tree
            if header.header_id in features.honey_tree_header_ids
            else None
        ),
        daily_encounter_pool=(
            features.great_marsh_pool
            if header.header_id in features.great_marsh_header_ids
            else features.trophy_garden_pool
            if header.header_id == features.trophy_garden_header_id
            else None
        ),
        game_corner_prizes=(
            features.game_corner_prizes
            if header.header_id == features.game_corner_header_id
            else ()
        ),
        provenance=RecordProvenance(
            source="rom", archive="arm9", member=header.header_id
        ),
        section_name=section_name,
        section_name_source=section_name_source,
    ).to_dict()


def _extract_event_map_location_pokemon_gifts(
    engine: LocationConcern,
    script: bytes,
    *,
    script_file_id: int,
    pokemon_names: tuple[str, ...],
    item_names: tuple[str, ...],
) -> tuple[LocationPokemonGift, ...]:
    gifts = []
    for command in engine.parse_pokemon_gift_commands(
        script, species_count=len(pokemon_names), item_count=len(item_names)
    ):
        held_item_id = command.held_item_id or None
        gifts.append(
            LocationPokemonGift(
                kind="pokemon",
                species_id=command.species_id,
                name=pokemon_names[command.species_id],
                level=command.level,
                held_item_id=held_item_id,
                held_item_name=(
                    item_names[held_item_id] if held_item_id is not None else None
                ),
                script_file_id=script_file_id,
                command_offset=command.offset,
            )
        )
    for command in engine.parse_egg_gift_commands(
        script, species_count=len(pokemon_names)
    ):
        gifts.append(
            LocationPokemonGift(
                kind="egg",
                species_id=command.species_id,
                name=pokemon_names[command.species_id],
                level=1,
                held_item_id=None,
                held_item_name=None,
                script_file_id=script_file_id,
                command_offset=command.offset,
            )
        )
    return tuple(sorted(gifts, key=lambda gift: gift.command_offset))


def _extract_event_map_location_static_encounters(
    engine: LocationConcern,
    script: bytes,
    *,
    script_file_id: int,
    map_header_id: int,
    script_is_shared: bool,
    explicit_header_by_command: dict[tuple[int, int], int],
    pokemon_names: tuple[str, ...],
) -> tuple[LocationStaticEncounter, ...]:
    encounters = []
    for command in engine.parse_static_encounter_commands(
        script, species_count=len(pokemon_names)
    ):
        command_key = (script_file_id, command.offset)
        explicit_header_id = explicit_header_by_command.get(command_key)
        if explicit_header_id is not None:
            if explicit_header_id != map_header_id:
                continue
        elif script_is_shared:
            raise ProfileError(
                "Static encounter in shared script member "
                f"{script_file_id} at 0x{command.offset:X} requires a map-header "
                "location override"
            )
        encounters.append(
            LocationStaticEncounter(
                species_id=command.species_id,
                name=pokemon_names[command.species_id],
                level=command.level,
                is_egg=False,
                command=command.command,
                script_file_id=script_file_id,
                command_offset=command.offset,
            )
        )
    return tuple(encounters)


def _extract_event_map_location_npc_trades(
    engine: LocationConcern,
    script: bytes,
    *,
    script_file_id: int,
    trade_records: tuple[Any, ...],
    trade_names: tuple[str, ...],
    pokemon_names: tuple[str, ...],
    item_names: tuple[str, ...],
) -> tuple[LocationNpcTrade, ...]:
    trades = []
    trade_count = len(trade_records)
    for command in engine.parse_npc_trade_commands(script, trade_count=trade_count):
        trade = trade_records[command.trade_id]
        held_item_id = trade.held_item_id
        trades.append(
            LocationNpcTrade(
                trade_id=command.trade_id,
                requested_species_id=trade.requested_species_id,
                requested_species_name=pokemon_names[trade.requested_species_id],
                offered_species_id=trade.offered_species_id,
                offered_species_name=pokemon_names[trade.offered_species_id],
                nickname=trade_names[command.trade_id],
                ivs=trade.ivs,
                nature=trade.nature,
                held_item_id=held_item_id,
                held_item_name=(
                    item_names[held_item_id] if held_item_id is not None else None
                ),
                ot_name=trade_names[trade_count + command.trade_id],
                ot_id=trade.ot_id,
                ot_gender="Female" if trade.ot_gender else "Male",
                language=engine.trade_language_name(trade.language_id),
                personality=trade.personality,
                contest_stats=trade.contest_stats,
                unused_values=trade.unused_values,
                script_file_id=script_file_id,
                command_offset=command.offset,
            )
        )
    return tuple(trades)


def _extract_event_map_location_script_awarded_items(
    engine: LocationConcern,
    script: bytes,
    *,
    script_file_id: int,
    item_names: tuple[str, ...],
) -> tuple[LocationScriptAwardedItem, ...]:
    """Resolve items an NPC's own dialogue script hands over directly.

    These never place an item-ball/hidden-item event on the map, so they are
    otherwise invisible to `extract_event_map_items` (e.g. a species-
    conditional gift from an "Item Fanatic"-style NPC).
    """
    return tuple(
        LocationScriptAwardedItem(
            item_id=award.item_id,
            name=item_names[award.item_id],
            quantity=award.quantity,
            script_file_id=script_file_id,
            command_offset=award.command_offset,
            command=award.command,
        )
        for award in engine.find_script_awarded_items(
            script, item_count=len(item_names)
        )
    )

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from functools import partial
from typing import Any

from romwiki.engines.concerns import LocationConcern
from romwiki.engines.registry import COMPRESSED_CODE_BINARY, get_engine
from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.pipeline.extraction.locations.helpers import (
    EventMapItemScan,
    extract_event_map_connections,
    extract_event_map_items,
    extract_trainer_references,
)
from romwiki.pipeline.extraction.map_headers import (
    read_code_binary,
    resolve_map_headers,
)
from romwiki.pipeline.extraction.trainers.support import scripts_archive_options
from romwiki.pipeline.semantics.location_sections import (
    resolve_location_section,
    validate_location_sections,
)
from romwiki.platforms.registry import get_platform
from romwiki.schema import (
    EncounterMapLocation,
    LocationMartReference,
    LocationPokemonGift,
    LocationScriptAwardedItem,
    LocationStaticEncounter,
    LocationWarp,
    RecordProvenance,
)
from romwiki.schema.versions import LOCATIONS_RAW_SCHEMA_VERSION
from romwiki.util.errors import InvalidRomError, ProfileError


@dataclass(frozen=True, slots=True)
class _PokemonGiftParsers:
    pokemon: Any
    egg: Any
    togepi_egg: Any
    togepi_species_id: int | None


def _resolve_pokemon_gift_parsers(
    engine: LocationConcern, pokemon_names: tuple[str, ...]
) -> _PokemonGiftParsers:
    # `GiveTogepiEgg` carries no species operand -- species identity comes
    # only from the opcode's own name, resolved against this profile's own
    # decoded Pokémon name table rather than a hardcoded ID, so a hack that
    # renumbers species is not silently mislabeled. Omitted entirely when the
    # current name table has no exact "TOGEPI" entry.
    togepi_species_id = next(
        (
            species_id
            for species_id, name in enumerate(pokemon_names)
            if name.strip().upper() == "TOGEPI"
        ),
        None,
    )
    return _PokemonGiftParsers(
        pokemon=engine.parse_pokemon_gift_commands,
        egg=engine.parse_egg_gift_commands,
        togepi_egg=engine.parse_togepi_egg_gift_commands,
        togepi_species_id=togepi_species_id,
    )


def _collect_pokemon_gifts(
    parsers: _PokemonGiftParsers,
    script_data: bytes,
    *,
    pokemon_names: tuple[str, ...],
    script_file_id: int,
) -> tuple[LocationPokemonGift, ...]:
    gifts: list[LocationPokemonGift] = []
    gifts.extend(
        LocationPokemonGift(
            kind="pokemon",
            species_id=command.species_id,
            name=pokemon_names[command.species_id],
            level=command.level,
            held_item_id=None,
            held_item_name=None,
            script_file_id=script_file_id,
            command_offset=command.offset,
        )
        for command in parsers.pokemon(script_data, species_count=len(pokemon_names))
    )
    gifts.extend(
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
        for command in parsers.egg(script_data, species_count=len(pokemon_names))
    )
    if parsers.togepi_species_id is not None:
        togepi_species_id = parsers.togepi_species_id
        gifts.extend(
            LocationPokemonGift(
                kind="egg",
                species_id=togepi_species_id,
                name=pokemon_names[togepi_species_id],
                level=1,
                held_item_id=None,
                held_item_name=None,
                script_file_id=script_file_id,
                command_offset=command.offset,
            )
            for command in parsers.togepi_egg(script_data)
        )
    return tuple(sorted(gifts, key=lambda gift: gift.command_offset))


def _script_keyed_records(
    headers: Iterable[Any],
    scripts: Any,
    *,
    build: Callable[[int, bytes], tuple[Any, ...]],
) -> dict[int, tuple[Any, ...]]:
    """Build a per-script-file record cache shared by every script-derived section.

    Each such section (script-awarded items, static encounters, Pokémon
    gifts, mart references) resolves the same way: dedupe by script file,
    bounds-check that file, then let the caller's `build` decode its own
    records from the script bytes.
    """
    records_by_script: dict[int, tuple[Any, ...]] = {}
    for header in headers:
        script_file_id = header.script_file_id
        if script_file_id in records_by_script:
            continue
        if script_file_id >= len(scripts.members):
            raise InvalidRomError(
                f"Map header {header.header_id} references missing script file "
                f"{script_file_id}"
            )
        records_by_script[script_file_id] = build(
            script_file_id, scripts.read(script_file_id)
        )
    return records_by_script


def _resolve_warps(
    header: Any,
    raw_warps: Iterable[Any],
    *,
    headers: Any,
    profile: Any,
    location_names: tuple[str, ...],
    dynamic_warp_header_id: int,
    dynamic_warp_id: int,
    raw_warps_by_header: dict[int, tuple[Any, ...]],
) -> tuple[LocationWarp, ...]:
    warps = []
    for warp in raw_warps:
        if (
            warp.destination_header_id == dynamic_warp_header_id
            and warp.destination_warp_id == dynamic_warp_id
        ):
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
        if warp.destination_header_id >= len(headers):
            raise InvalidRomError(
                f"Map header {header.header_id} warp {warp.index} references "
                f"missing header {warp.destination_header_id}"
            )
        destination = headers[warp.destination_header_id]
        destination_section_name, _ = resolve_location_section(
            profile,
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
                destination_name=location_names[destination.location_name_id],
                destination_section_name=destination_section_name,
                destination_internal_name=destination.internal_name,
                destination_warp_exists=(
                    warp.destination_warp_id
                    < len(raw_warps_by_header[destination.header_id])
                ),
                dynamic=False,
            )
        )
    return tuple(warps)


@dataclass(frozen=True, slots=True)
class _Arm9EncounterMapLayout:
    map_names_path: str
    messages_path: str
    encounters_path: str
    events_path: str
    matrices_path: str
    scripts_path: str
    count: int
    table_offset: int
    location_names_member: int
    item_names_member: int


@dataclass(frozen=True, slots=True)
class _Arm9EncounterMapSentinels:
    null_encounter_id: int
    null_event_id: int
    dynamic_warp_header_id: int
    dynamic_warp_id: int
    matrix_void_header_ids: frozenset[int]


@dataclass(frozen=True, slots=True)
class _Arm9EncounterMapSource:
    profile: Any
    engine: Any
    layout: _Arm9EncounterMapLayout
    encounters: Any
    events: Any
    matrices: Any
    scripts: Any
    arm9_data: bytes
    headers: tuple[Any, ...]
    location_names: tuple[str, ...]
    item_names: tuple[str, ...]
    pokemon_names: tuple[str, ...]
    sentinels: _Arm9EncounterMapSentinels


@dataclass(frozen=True, slots=True)
class _Arm9EncounterMapEvents:
    raw_warps_by_header: dict[int, tuple[Any, ...]]
    items_by_event: dict[int, EventMapItemScan]


@dataclass(frozen=True, slots=True)
class _Arm9EncounterMapScriptRecords:
    script_awarded_items: dict[int, tuple[Any, ...]]
    static_encounters: dict[int, tuple[Any, ...]]
    pokemon_gifts: dict[int, tuple[Any, ...]]
    mart_references: dict[int, tuple[Any, ...]]


def extract_arm9_encounter_map_location_dataset(
    result: InspectionResult,
    trainer_dataset: dict[str, Any] | None = None,
    item_dataset: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source = _load_arm9_encounter_map_source(result, item_dataset)
    events = _scan_map_events(source)
    script_records = _collect_script_records(source)
    connections = extract_event_map_connections(
        source.engine,
        source.headers,
        source.matrices,
        source.location_names,
        source.sentinels.matrix_void_header_ids,
    )
    trainers = extract_trainer_references(result, trainer_dataset)
    records = [
        _build_arm9_encounter_map_record(
            source,
            header,
            events,
            script_records,
            connections=connections,
            trainers=trainers,
        )
        for header in source.headers
    ]
    return _build_arm9_encounter_map_envelope(result, source, events, records)


def _read_arm9_encounter_map_layout(profile: Any) -> _Arm9EncounterMapLayout:
    try:
        return _Arm9EncounterMapLayout(
            map_names_path=profile.layout["map_names"],
            messages_path=profile.layout["messages"],
            encounters_path=profile.layout["encounters"],
            events_path=profile.layout["events"],
            matrices_path=profile.layout["map_matrices"],
            scripts_path=profile.layout["scripts"],
            count=profile.parameters["map_header_count"],
            table_offset=profile.parameters["map_header_offset"],
            location_names_member=profile.parameters["location_names_member"],
            item_names_member=profile.parameters["item_names_member"],
        )
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} is missing location metadata: {error.args[0]}"
        ) from error


def _load_arm9_encounter_map_source(
    result: InspectionResult, item_dataset: dict[str, Any] | None
) -> _Arm9EncounterMapSource:
    assert result.match is not None
    profile = result.match.profile
    layout = _read_arm9_encounter_map_layout(profile)

    platform = get_platform(profile.platform)
    if platform.filesystem_from_image is None or platform.archive_cls is None:
        raise ProfileError(
            f"Platform {profile.platform!r} does not support archive-based extraction"
        )
    engine = get_engine(profile.engine).locations
    filesystem = platform.filesystem_from_image(result.image)
    messages = platform.archive_cls.from_bytes(
        filesystem.read(layout.messages_path),
        allow_truncated=profile.parameters.get("messages_allow_truncated", False),
    )
    encounters = platform.archive_cls.from_bytes(
        filesystem.read(layout.encounters_path),
        allow_truncated=profile.parameters.get("encounters_allow_truncated", False),
    )
    event_options = {}
    if profile.parameters.get("events_allow_incorrect_data_block_size", False):
        event_options["allow_incorrect_data_block_size"] = True
    events = platform.archive_cls.from_bytes(
        filesystem.read(layout.events_path), **event_options
    )
    matrices = platform.archive_cls.from_bytes(filesystem.read(layout.matrices_path))
    scripts = platform.archive_cls.from_bytes(
        filesystem.read(layout.scripts_path), **scripts_archive_options(profile)
    )
    arm9_data = read_code_binary(
        platform,
        result.image,
        compressed=COMPRESSED_CODE_BINARY in get_engine(profile.engine).capabilities,
    )
    headers, location_names = resolve_map_headers(
        engine,
        arm9_data,
        filesystem,
        messages,
        map_names_path=layout.map_names_path,
        table_offset=layout.table_offset,
        count=layout.count,
        location_names_member=layout.location_names_member,
    )
    validate_location_sections(
        profile,
        ((header.header_id, header.internal_name) for header in headers),
    )
    sentinels = _resolve_arm9_encounter_map_sentinels(profile, engine)
    item_names = tuple(
        record["name"] for record in (item_dataset or {}).get("records", ())
    ) or engine.parse_english_message_archive(messages.read(layout.item_names_member))
    pokemon_names_member = profile.optional_int_parameter("pokemon_names_member")
    return _Arm9EncounterMapSource(
        profile=profile,
        engine=engine,
        layout=layout,
        encounters=encounters,
        events=events,
        matrices=matrices,
        scripts=scripts,
        arm9_data=arm9_data,
        headers=headers,
        location_names=location_names,
        item_names=item_names,
        pokemon_names=(
            engine.parse_english_message_archive(messages.read(pokemon_names_member))
            if pokemon_names_member is not None
            else ()
        ),
        sentinels=sentinels,
    )


def _resolve_arm9_encounter_map_sentinels(
    profile: Any, engine: LocationConcern
) -> _Arm9EncounterMapSentinels:
    return _Arm9EncounterMapSentinels(
        null_encounter_id=profile.int_parameter(
            "null_encounter_id", engine.ENCOUNTER_MEMBER_NONE
        ),
        null_event_id=profile.int_parameter(
            "null_event_id", engine.ARCHIVE_MEMBER_NONE
        ),
        dynamic_warp_header_id=profile.int_parameter(
            "dynamic_warp_header_id", engine.DYNAMIC_WARP_HEADER_ID
        ),
        dynamic_warp_id=profile.int_parameter(
            "dynamic_warp_id", engine.DYNAMIC_WARP_ID
        ),
        matrix_void_header_ids=frozenset(
            profile.parameters.get(
                "matrix_void_header_ids", engine.MATRIX_VOID_HEADER_IDS
            )
        ),
    )


def _scan_map_events(source: _Arm9EncounterMapSource) -> _Arm9EncounterMapEvents:
    engine = source.engine
    parsed_events: dict[int, Any] = {}
    items_by_event: dict[int, EventMapItemScan] = {}
    raw_warps_by_header: dict[int, tuple[Any, ...]] = {}
    empty_item_scan = EventMapItemScan(
        items=(), unresolved_visible_count=0, unresolved_hidden_count=0
    )
    visible_item_ids = engine.parse_item_ball_table(
        source.scripts.read(engine.ITEM_BALL_TABLE_SCRIPT_MEMBER)
    )
    hidden_item_ids = engine.parse_hidden_item_table(
        source.arm9_data, item_count=len(source.item_names)
    )
    for header in source.headers:
        if header.event_file_id == source.sentinels.null_event_id:
            raw_warps_by_header[header.header_id] = ()
            continue
        if header.event_file_id >= len(source.events.members):
            raise InvalidRomError(
                f"Map header {header.header_id} references missing event file "
                f"{header.event_file_id}"
            )
        if header.event_file_id not in parsed_events:
            parsed = engine.parse_map_events(
                source.events.read(header.event_file_id),
                event_file_id=header.event_file_id,
            )
            parsed_events[header.event_file_id] = parsed
            items_by_event[header.event_file_id] = (
                extract_event_map_items(
                    engine,
                    parsed,
                    source.item_names,
                    visible_item_ids=visible_item_ids,
                    hidden_item_ids=hidden_item_ids,
                )
                if source.item_names
                else empty_item_scan
            )
        raw_warps_by_header[header.header_id] = parsed_events[
            header.event_file_id
        ].warps
    return _Arm9EncounterMapEvents(
        raw_warps_by_header=raw_warps_by_header, items_by_event=items_by_event
    )


def _collect_script_records(
    source: _Arm9EncounterMapSource,
) -> _Arm9EncounterMapScriptRecords:
    engine = source.engine
    script_awarded_items = _script_keyed_records(
        source.headers,
        source.scripts,
        build=partial(_build_script_awarded_items, engine, source.item_names),
    )
    static_encounters = _script_keyed_records(
        source.headers,
        source.scripts,
        build=partial(_build_static_encounters, engine, source.pokemon_names),
    )
    gift_parsers = _resolve_pokemon_gift_parsers(engine, source.pokemon_names)
    pokemon_gifts = _script_keyed_records(
        source.headers,
        source.scripts,
        build=partial(_build_pokemon_gifts, gift_parsers, source.pokemon_names),
    )
    mart_references = _script_keyed_records(
        source.headers,
        source.scripts,
        build=partial(_build_mart_references, engine),
    )
    return _Arm9EncounterMapScriptRecords(
        script_awarded_items=script_awarded_items,
        static_encounters=static_encounters,
        pokemon_gifts=pokemon_gifts,
        mart_references=mart_references,
    )


def _build_script_awarded_items(
    engine: LocationConcern,
    item_names: tuple[str, ...],
    script_file_id: int,
    data: bytes,
) -> tuple[LocationScriptAwardedItem, ...]:
    return tuple(
        LocationScriptAwardedItem(
            item_id=award.item_id,
            name=item_names[award.item_id],
            quantity=award.quantity,
            script_file_id=script_file_id,
            command_offset=award.command_offset,
            command=award.command,
        )
        for award in engine.find_script_awarded_items(data, item_count=len(item_names))
    )


def _build_static_encounters(
    engine: LocationConcern,
    pokemon_names: tuple[str, ...],
    script_file_id: int,
    data: bytes,
) -> tuple[LocationStaticEncounter, ...]:
    return tuple(
        LocationStaticEncounter(
            species_id=command.species_id,
            name=pokemon_names[command.species_id],
            level=command.level,
            is_egg=False,
            command=command.command,
            script_file_id=script_file_id,
            command_offset=command.offset,
        )
        for command in engine.parse_static_encounter_commands(
            data, species_count=len(pokemon_names)
        )
    )


def _build_pokemon_gifts(
    parsers: _PokemonGiftParsers,
    pokemon_names: tuple[str, ...],
    script_file_id: int,
    data: bytes,
) -> tuple[LocationPokemonGift, ...]:
    return _collect_pokemon_gifts(
        parsers,
        data,
        pokemon_names=pokemon_names,
        script_file_id=script_file_id,
    )


def _build_mart_references(
    engine: LocationConcern, script_file_id: int, data: bytes
) -> tuple[LocationMartReference, ...]:
    return tuple(
        LocationMartReference(
            kind=command.kind,
            inventory_id=command.inventory_id,
            script_file_id=script_file_id,
            command_offset=command.offset,
        )
        for command in engine.parse_mart_dispatch_commands(data)
    )


def _build_arm9_encounter_map_record(
    source: _Arm9EncounterMapSource,
    header: Any,
    events: _Arm9EncounterMapEvents,
    script_records: _Arm9EncounterMapScriptRecords,
    *,
    connections: dict[int, list[Any]],
    trainers: dict[int, list[Any]],
) -> dict[str, Any]:
    section_name, section_name_source = resolve_location_section(
        source.profile,
        header_id=header.header_id,
        internal_name=header.internal_name,
    )
    encounter_id = header.encounter_id
    encounter_map_index = (
        None if encounter_id == source.sentinels.null_encounter_id else encounter_id
    )
    if encounter_map_index is not None and encounter_map_index >= len(
        source.encounters.members
    ):
        raise InvalidRomError(
            f"Map header {header.header_id} references missing encounter "
            f"member {encounter_map_index}"
        )
    warps = _resolve_warps(
        header,
        events.raw_warps_by_header[header.header_id],
        headers=source.headers,
        profile=source.profile,
        location_names=source.location_names,
        dynamic_warp_header_id=source.sentinels.dynamic_warp_header_id,
        dynamic_warp_id=source.sentinels.dynamic_warp_id,
        raw_warps_by_header=events.raw_warps_by_header,
    )
    script_file_id = header.script_file_id
    return EncounterMapLocation(
        header_id=header.header_id,
        name=source.location_names[header.location_name_id],
        encounter_map_index=encounter_map_index,
        matrix_id=header.matrix_id,
        internal_name=header.internal_name,
        section_name=section_name,
        section_name_source=section_name_source,
        trainers=tuple(trainers.get(header.header_id, ())),
        warps=warps,
        connections=tuple(connections.get(header.header_id, ())),
        items=(
            ()
            if header.event_file_id == source.sentinels.null_event_id
            else events.items_by_event[header.event_file_id].items
        ),
        script_awarded_items=script_records.script_awarded_items.get(
            script_file_id, ()
        ),
        static_encounters=script_records.static_encounters.get(script_file_id, ()),
        pokemon_gifts=script_records.pokemon_gifts.get(script_file_id, ()),
        mart_references=script_records.mart_references.get(script_file_id, ()),
        provenance=RecordProvenance(
            source="rom", archive="arm9", member=header.header_id
        ),
    ).to_dict()


def _build_arm9_encounter_map_envelope(
    result: InspectionResult,
    source: _Arm9EncounterMapSource,
    events: _Arm9EncounterMapEvents,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    layout = source.layout
    items_by_event = events.items_by_event
    return {
        "schema_version": LOCATIONS_RAW_SCHEMA_VERSION,
        "game": source.profile.id,
        "engine": source.profile.engine,
        "dataset": "locations",
        "record_count": len(records),
        "warp_count": sum(len(record["warps"]) for record in records),
        "connection_count": sum(len(record["connections"]) for record in records),
        "visible_item_count": sum(
            item["kind"] == "visible" for record in records for item in record["items"]
        ),
        "hidden_item_count": sum(
            item["kind"] == "hidden" for record in records for item in record["items"]
        ),
        "unresolved_visible_item_count": sum(
            scan.unresolved_visible_count for scan in items_by_event.values()
        ),
        "unresolved_hidden_item_count": sum(
            scan.unresolved_hidden_count for scan in items_by_event.values()
        ),
        "script_awarded_item_reference_count": sum(
            len(record["script_awarded_items"]) for record in records
        ),
        "static_encounter_reference_count": sum(
            len(record["static_encounters"]) for record in records
        ),
        "pokemon_gift_reference_count": sum(
            len(record["pokemon_gifts"]) for record in records
        ),
        "mart_reference_count": sum(
            len(record["mart_references"]) for record in records
        ),
        "source": {
            "rom_sha256": result.image.hashes.sha256,
            "map_headers": {"arm9_offset": layout.table_offset, "count": layout.count},
            "internal_names": layout.map_names_path,
            "events_archive": layout.events_path,
            "map_matrices_archive": layout.matrices_path,
            "scripts_archive": layout.scripts_path,
            "location_names": {
                "archive": layout.messages_path,
                "member": layout.location_names_member,
            },
            "item_names": {
                "archive": layout.messages_path,
                "member": layout.item_names_member,
            },
        },
        "records": records,
    }

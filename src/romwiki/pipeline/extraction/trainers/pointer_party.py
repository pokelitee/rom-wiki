from __future__ import annotations

import struct
from dataclasses import replace
from typing import Any, cast

from romwiki.engines.registry import get_engine
from romwiki.engines.trainer_variants import (
    TrainerVariantResolver,
    resolve_trainer_variants,
)
from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.pipeline.extraction.map_headers import iter_gba_map_headers
from romwiki.platforms.registry import get_platform
from romwiki.schema.datasets import dataset_envelope
from romwiki.schema.trainers import TrainerLocation
from romwiki.schema.versions import (
    TRAINER_BATTLE_FAMILY_SCHEMA_VERSION,
    TRAINERS_RAW_SCHEMA_VERSION,
)
from romwiki.util.errors import ProfileError

# Party-flags byte and party-size byte within one trainer header record --
# needed here (ahead of the engine's own `parse_trainer_record`) to size the
# separate `platform.read_bytes` call for that trainer's party data, which
# lives at a ROM pointer stored inside the header, not at a fixed offset
# relative to it. See `engines/gen3/frlg/trainers.py`'s module comment for
# the full verified header/party layout.
_PARTY_FLAGS_OFFSET = 0x00
_PARTY_SIZE_OFFSET = 0x20
_PARTY_POINTER_OFFSET = 0x24


def extract_pointer_party_trainer_dataset(result: InspectionResult) -> dict[str, Any]:
    if result.match is None:
        raise ProfileError("A known game profile is required for trainer extraction")
    profile = result.match.profile
    try:
        offset = profile.parameters["trainer_offset"]
        count = profile.parameters["trainer_count"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} does not define trainer_offset/trainer_count"
        ) from error
    if not isinstance(offset, int) or not isinstance(count, int):
        raise ProfileError(f"Profile {profile.id} has an invalid trainer parameter")

    platform = get_platform(profile.platform)
    if platform.read_bytes is None:
        raise ProfileError(f"Platform {profile.platform!r} does not support flat reads")
    engine = get_engine(profile.engine).trainers
    record_size = engine.TRAINER_RECORD_SIZE
    header_data = platform.read_bytes(result.image, offset, record_size * count)
    archive_path = f"offset:{offset:#x}"

    parsed_records = []
    for trainer_id in range(count):
        header = header_data[trainer_id * record_size : (trainer_id + 1) * record_size]
        party_flags = header[_PARTY_FLAGS_OFFSET]
        party_size = header[_PARTY_SIZE_OFFSET]
        party_pointer = struct.unpack_from("<I", header, _PARTY_POINTER_OFFSET)[0]
        has_custom_moves = bool(party_flags & 1)
        party_size_bytes = (
            engine.party_record_size(has_custom_moves=has_custom_moves) * party_size
        )
        if party_size == 0:
            party_data = b""
        else:
            party_offset = engine.resolve_gba_pointer(party_pointer)
            party_data = platform.read_bytes(
                result.image, party_offset, party_size_bytes
            )
        record = engine.parse_trainer_record(
            header,
            party_data,
            trainer_id=trainer_id,
            archive_path=archive_path,
        )
        parsed_records.append(record)

    # Only trainers placed as overworld objects whose script starts the
    # battle can be linked; rematches and scripted battles keep no location.
    locations_by_trainer = _extract_gen3_trainer_locations(platform, result, profile)
    records = [
        replace(
            record, locations=tuple(locations_by_trainer.get(record.trainer_id, ()))
        ).to_dict()
        for record in parsed_records
    ]

    variant_contract = resolve_trainer_variants(
        cast(TrainerVariantResolver, engine),
        profile.id,
        profile.parameters,
        records,
        None,
    )
    envelope = dataset_envelope(
        schema_version=TRAINERS_RAW_SCHEMA_VERSION,
        game=profile.id,
        engine=profile.engine,
        dataset="trainers",
        source={"rom_sha256": result.image.hashes.sha256, "offset": offset},
        records=records,
    )
    envelope["battle_family_schema_version"] = TRAINER_BATTLE_FAMILY_SCHEMA_VERSION
    envelope.update(variant_contract)
    envelope["linked_record_count"] = len(locations_by_trainer)
    envelope["location_reference_count"] = sum(
        len(locations) for locations in locations_by_trainer.values()
    )
    envelope["script_reference_count"] = 0
    item_names = _item_names(
        profile, platform, result, engine=get_engine(profile.engine)
    )
    if item_names is not None:
        envelope["item_names"] = item_names
    return envelope


def _extract_gen3_trainer_locations(
    platform: Any, result: InspectionResult, profile: Any
) -> dict[int, tuple[TrainerLocation, ...]]:
    """Link each Generation III trainer to the map it's placed on as an
    overworld object, by decoding that map's `MapEvents`/
    `ObjectEventTemplate` chain and matching each trainer-type object's
    leading `trainerbattle` script command against a trainer ID (see
    `engines/gen3/shared/overworld.py`'s module comment for how this was
    verified against real ROM data).

    Reads every map through `gMapGroups`, like the `locations` domain,
    rather than depending on its output. Optional: a profile without
    `gmapgroups_offset` leaves every trainer's `locations` empty.
    """
    engine = get_engine(profile.engine).trainers
    if "gmapgroups_offset" not in profile.parameters:
        return {}

    locations: dict[int, list[TrainerLocation]] = {}
    for header in iter_gba_map_headers(engine, platform, result.image, profile):
        events_pointer = struct.unpack_from("<I", header.data, 0x04)[0]
        if events_pointer != 0:
            _link_gen3_trainer_objects(
                platform,
                result,
                engine,
                events_pointer,
                header_id=header.header_id,
                name=header.name,
                locations=locations,
            )
    return {trainer_id: tuple(entries) for trainer_id, entries in locations.items()}


def _link_gen3_trainer_objects(
    platform: Any,
    result: InspectionResult,
    engine: Any,
    events_pointer: int,
    *,
    header_id: int,
    name: str,
    locations: dict[int, list[TrainerLocation]],
) -> None:
    events_offset = engine.resolve_gba_pointer(events_pointer)
    events_data = platform.read_bytes(
        result.image, events_offset, engine.overworld.MAP_EVENTS_SIZE
    )
    object_event_count, object_events_pointer = engine.parse_map_events(
        events_data, header_id=header_id
    )
    if object_event_count == 0 or object_events_pointer == 0:
        return
    object_events_offset = engine.resolve_gba_pointer(object_events_pointer)
    template_size = engine.overworld.OBJECT_EVENT_TEMPLATE_SIZE
    object_events_data = platform.read_bytes(
        result.image, object_events_offset, template_size * object_event_count
    )
    for index in range(object_event_count):
        raw = object_events_data[index * template_size : (index + 1) * template_size]
        local_id, kind, x, y, elevation, trainer_type, script_pointer = (
            engine.parse_object_event_template(raw, header_id=header_id, index=index)
        )
        # Objects that never walk up to the player, such as Emerald's Gym
        # Leaders, have trainer type 0 but still start a `trainerbattle`.
        if kind != 0 or script_pointer == 0:
            continue
        script_offset = engine.resolve_gba_pointer(script_pointer)
        script_data = platform.read_bytes(result.image, script_offset, 4)
        trainer_id = engine.decode_trainerbattle_id(script_data)
        if trainer_id is None:
            continue
        locations.setdefault(trainer_id, []).append(
            TrainerLocation(
                header_id=header_id,
                internal_name="",
                location_name_id=header_id,
                name=name,
                # Generation III has no archive/file-member concept for
                # overworld objects (they're a flat ROM-address array per
                # map header, not indexed archive members like the NDS
                # engines' `overworld_file_id`) -- 0 rather than a guessed
                # index.
                event_file_id=0,
                object_index=index,
                object_local_id=local_id,
                script_id=script_offset,
                trainer_type=trainer_type,
                x=x,
                y=y,
                z=elevation,
            )
        )


def _item_names(
    profile: Any, platform: Any, result: InspectionResult, *, engine: Any
) -> list[str] | None:
    """Decode item display names for `pipeline/enrichment/references.py`'s
    `item_reference` to resolve held/AI-battle/victory item IDs against.

    Reference-name extraction (`pipeline/extraction/reference_names.py`) is
    unconditionally NDS/archive-shaped and never runs for this platform, so
    `item_reference` would otherwise fall back to a raw-ID PokeDB lookup --
    which doesn't match Generation III's own item numbering (the same class
    of mismatch already documented in `personal.py`'s `wild_held_items`
    comment). Item names are decoded inline per-item (see
    `engines/gen3/frlg/items.py`), not from a separate name table, so this
    re-reads just the name field of the same item table `items.py` decodes
    -- a small, independent read, not a dependency on the enriched items
    build (which itself depends on the enriched trainers dataset for
    cross-referencing; depending on it here would be circular).
    """
    item_offset = profile.optional_int_parameter("item_offset")
    item_count = profile.optional_int_parameter("item_count")
    if item_offset is None or item_count is None:
        return None
    record_size = engine.items.ITEM_RECORD_SIZE
    data = platform.read_bytes(result.image, item_offset, record_size * item_count)
    return engine.items.decode_gen3_text_table(
        data, stride=record_size, count=item_count
    )

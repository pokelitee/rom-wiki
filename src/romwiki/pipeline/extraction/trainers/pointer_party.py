from __future__ import annotations

import struct
from typing import Any, cast

from romwiki.engines.registry import get_engine
from romwiki.engines.trainer_variants import (
    TrainerVariantResolver,
    resolve_trainer_variants,
)
from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.platforms.registry import get_platform
from romwiki.schema.datasets import dataset_envelope
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
    decoded_count = min(count, engine.TRAINER_RECORD_COUNT)
    header_data = platform.read_bytes(result.image, offset, record_size * decoded_count)
    archive_path = f"offset:{offset:#x}"

    records = []
    for trainer_id in range(decoded_count):
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
        # No overworld/script system decoded for Generation III yet (see
        # the plan's Context section) -- `parse_trainer_record` leaves
        # `locations`/`script_references` at their dataclass defaults
        # (both `()`) rather than guessing where a trainer battle triggers.
        record = engine.parse_trainer_record(
            header,
            party_data,
            trainer_id=trainer_id,
            archive_path=archive_path,
        )
        records.append(record.to_dict())

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
    envelope["linked_record_count"] = 0
    envelope["location_reference_count"] = 0
    envelope["script_reference_count"] = 0
    item_names = _item_names(
        profile, platform, result, engine=get_engine(profile.engine)
    )
    if item_names is not None:
        envelope["item_names"] = item_names
    return envelope


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
    item_offset = profile.parameters.get("item_offset")
    item_count = profile.parameters.get("item_count")
    if not isinstance(item_offset, int) or not isinstance(item_count, int):
        return None
    record_size = engine.items.ITEM_RECORD_SIZE
    decoded_count = min(item_count, engine.items.ITEM_RECORD_COUNT)
    data = platform.read_bytes(result.image, item_offset, record_size * decoded_count)
    return engine.items.decode_gen3_text_table(
        data, stride=record_size, count=decoded_count
    )

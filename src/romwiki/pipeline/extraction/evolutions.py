from __future__ import annotations

from typing import Any

from romwiki.engines.registry import get_engine
from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.platforms.registry import get_platform
from romwiki.schema.datasets import dataset_envelope
from romwiki.schema.versions import POKEMON_EVOLUTIONS_RAW_SCHEMA_VERSION
from romwiki.util.errors import ProfileError


def extract_evolution_dataset(result: InspectionResult) -> dict[str, Any]:
    if result.match is None:
        raise ProfileError("A known game profile is required for evolution extraction")
    profile = result.match.profile
    platform = get_platform(profile.platform)
    if platform.archive_cls is None and platform.read_bytes is not None:
        return _extract_evolution_dataset_flat(result, profile, platform)
    try:
        archive_path = profile.layout["evolutions"]
        message_archive_path = profile.layout["messages"]
        item_names_member = profile.parameters["item_names_member"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} does not define evolution item-name data"
        ) from error

    if platform.filesystem_from_image is None or platform.archive_cls is None:
        raise ProfileError(
            f"Platform {profile.platform!r} does not support archive-based extraction"
        )
    adapter = get_engine(profile.engine)
    engine = adapter.evolutions
    filesystem = platform.filesystem_from_image(result.image)
    archive = platform.archive_cls.from_bytes(
        filesystem.read(archive_path),
        allow_truncated=profile.parameters.get("evolutions_allow_truncated", False),
    )
    message_archive = platform.archive_cls.from_bytes(
        filesystem.read(message_archive_path),
        allow_truncated=profile.parameters.get("messages_allow_truncated", False),
    )
    item_names = engine.parse_english_message_archive(
        message_archive.read(item_names_member)
    )
    records = [
        engine.parse_evolution_record(
            archive.read(member.index),
            species_id=member.index,
            archive_path=archive_path,
        ).to_dict()
        for member in archive.members[: adapter.personal.PERSONAL_RECORD_COUNT]
    ]
    envelope = dataset_envelope(
        schema_version=POKEMON_EVOLUTIONS_RAW_SCHEMA_VERSION,
        game=profile.id,
        engine=profile.engine,
        dataset="evolutions",
        source={
            "rom_sha256": result.image.hashes.sha256,
            "archive": archive_path,
            "item_names": {
                "archive": message_archive_path,
                "member": item_names_member,
            },
        },
        records=records,
    )
    envelope["item_names"] = list(item_names)
    return envelope


def _extract_evolution_dataset_flat(
    result: InspectionResult, profile: Any, platform: Any
) -> dict[str, Any]:
    try:
        offset = profile.parameters["evolution_offset"]
        personal_count = profile.parameters["personal_count"]
        item_offset = profile.parameters["item_offset"]
        item_count = profile.parameters["item_count"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} does not define evolution_offset/personal_count/"
            "item_offset/item_count"
        ) from error

    engine = get_engine(profile.engine).evolutions
    record_size = engine.EVOLUTION_RECORD_SIZE
    data = platform.read_bytes(result.image, offset, record_size * personal_count)
    archive_path = f"offset:{offset:#x}"
    decoded_count = min(personal_count, engine.PERSONAL_RECORD_COUNT)
    records = [
        engine.parse_evolution_record(
            data[index * record_size : (index + 1) * record_size],
            species_id=index,
            archive_path=archive_path,
        ).to_dict()
        for index in range(decoded_count)
    ]

    # Item display names are decoded inline per-item (see
    # `engines/gen3/frlg/items.py`), not from a separate message archive --
    # this re-reads just the name field of the same item table `items.py`
    # decodes, the same small independent read
    # `trainers/pointer_party.py`'s `_item_names` already does for held/AI-
    # battle item resolution.
    item_record_size = engine.ITEM_RECORD_SIZE
    item_decoded_count = min(item_count, engine.ITEM_RECORD_COUNT)
    item_data = platform.read_bytes(
        result.image, item_offset, item_record_size * item_decoded_count
    )
    item_names = engine.decode_gen3_text_table(
        item_data, stride=item_record_size, count=item_decoded_count
    )

    envelope = dataset_envelope(
        schema_version=POKEMON_EVOLUTIONS_RAW_SCHEMA_VERSION,
        game=profile.id,
        engine=profile.engine,
        dataset="evolutions",
        source={
            "rom_sha256": result.image.hashes.sha256,
            "offset": offset,
            "item_names": {"offset": item_offset},
        },
        records=records,
    )
    envelope["item_names"] = list(item_names)
    return envelope

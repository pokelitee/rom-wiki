from __future__ import annotations

from dataclasses import asdict
from typing import Any

from romwiki.engines.concerns import ItemConcern
from romwiki.engines.registry import COMPRESSED_CODE_BINARY, get_engine
from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.pipeline.extraction.map_headers import read_code_binary
from romwiki.pipeline.extraction.reference_names import extract_reference_descriptions
from romwiki.platforms.registry import get_platform
from romwiki.schema.datasets import dataset_envelope
from romwiki.schema.versions import (
    ITEMS_RAW_SCHEMA_VERSION,
)
from romwiki.util.errors import DataSourceError, ProfileError
from romwiki.util.text import name_slug


def extract_item_dataset(result: InspectionResult) -> dict[str, Any]:
    if result.match is None:
        raise ProfileError("A known game profile is required for item extraction")
    profile = result.match.profile
    platform = get_platform(profile.platform)

    if platform.archive_cls is not None:
        return _extract_item_dataset_archive(result, profile, platform)
    if platform.read_bytes is not None:
        return _extract_item_dataset_flat(result, profile, platform)
    raise ProfileError(
        f"Platform {profile.platform!r} supports neither archive nor flat reads"
    )


def _extract_item_dataset_flat(
    result: InspectionResult, profile: Any, platform: Any
) -> dict[str, Any]:
    try:
        offset = profile.parameters["item_offset"]
        count = profile.parameters["item_count"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} does not define item_offset/item_count"
        ) from error
    if not isinstance(offset, int) or not isinstance(count, int):
        raise ProfileError(f"Profile {profile.id} has an invalid item parameter")

    engine = get_engine(profile.engine).items
    record_size = engine.ITEM_RECORD_SIZE
    data = platform.read_bytes(result.image, offset, record_size * count)
    archive_path = f"offset:{offset:#x}"
    decoded_count = min(count, engine.ITEM_RECORD_COUNT)

    records = []
    descriptions = []
    for item_id in range(decoded_count):
        record_bytes = data[item_id * record_size : (item_id + 1) * record_size]
        parsed = engine.parse_item_record(
            record_bytes, item_id=item_id, archive_path=archive_path
        ).to_dict()
        name = engine.item_name(record_bytes)
        pocket_id = parsed["field_pocket_id"]
        if pocket_id >= len(engine.ITEM_POCKET_NAMES):
            raise DataSourceError(f"Unknown item pocket ID: {pocket_id}")
        records.append(
            {
                **parsed,
                "name": name,
                "public": item_id > 0 and name != "",
                "revives_into_species_id": None,
                "berry": None,
                "pocket": {
                    "id": pocket_id,
                    "name": engine.ITEM_POCKET_NAMES[pocket_id],
                },
            }
        )
        descriptions.append(
            _decode_item_description(engine, platform, result, record_bytes)
        )

    envelope = dataset_envelope(
        schema_version=ITEMS_RAW_SCHEMA_VERSION,
        game=profile.id,
        engine=profile.engine,
        dataset="items",
        source={"rom_sha256": result.image.hashes.sha256, "offset": offset},
        records=records,
    )
    envelope["public_record_count"] = sum(record["public"] for record in records)
    envelope["item_descriptions"] = descriptions
    return envelope


def _decode_item_description(
    engine: ItemConcern, platform: Any, result: InspectionResult, record_bytes: bytes
) -> str:
    # Each item's description lives at its own inline ROM pointer (see
    # `engines/gen3/frlg/items.py`'s `item_description_pointer`), not a
    # shared table -- a generously-sized read (description text is at most
    # a handful of short lines) lets `decode_gen3_text` find the real
    # 0xFF terminator regardless of the exact string length.
    pointer = engine.item_description_pointer(record_bytes)
    if pointer == 0:
        return ""
    offset = engine.resolve_gba_pointer(pointer)
    data = platform.read_bytes(result.image, offset, 256)
    return engine.decode_gen3_text(data)


def _extract_item_dataset_archive(
    result: InspectionResult, profile: Any, platform: Any
) -> dict[str, Any]:
    try:
        item_archive_path = profile.layout["item_data"]
        message_archive_path = profile.layout["messages"]
        item_names_member = profile.parameters["item_names_member"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} is missing item metadata: {error.args[0]}"
        ) from error
    type_names_member = profile.parameters.get("type_names_member")

    adapter = get_engine(profile.engine)
    engine = adapter.items
    filesystem = platform.filesystem_from_image(result.image)
    item_archive = _open_archive(
        profile, platform, filesystem, item_archive_path, "items_allow_truncated"
    )
    messages = _open_archive(
        profile, platform, filesystem, message_archive_path, "messages_allow_truncated"
    )
    item_names = engine.parse_english_message_archive(messages.read(item_names_member))
    reference_descriptions = extract_reference_descriptions(
        profile, filesystem, messages, fields={"item_descriptions"}
    )
    type_names = _resolve_type_names(adapter, messages, type_names_member)

    source: dict[str, Any] = {
        "rom_sha256": result.image.hashes.sha256,
        "archive": item_archive_path,
        "item_names": {
            "archive": message_archive_path,
            "member": item_names_member,
        },
    }

    code_binary = _CodeBinary(platform, result.image, adapter)
    data_members, source["item_archive_map"] = _resolve_item_archive_members(
        engine,
        code_binary,
        adapter.formats.item_archive,
        item_count=len(item_names),
        data_member_count=len(item_archive.members),
    )

    if type_names_member is not None:
        source["type_names"] = {
            "archive": message_archive_path,
            "member": type_names_member,
        }

    revives_into_by_item, fossil_revival_source = _extract_fossil_revivals(
        profile,
        platform,
        filesystem,
        engine,
        code_binary,
        adapter.formats.fossils,
        item_count=len(item_names),
    )
    if fossil_revival_source is not None:
        source["fossil_revival_table"] = fossil_revival_source

    berry_by_item, berry_source = _extract_berry_data(
        profile, platform, filesystem, engine
    )
    if berry_source is not None:
        source["berry_data"] = berry_source

    records = [
        _build_archive_item_record(
            engine,
            engine.parse_item_record(
                item_archive.read(data_member),
                item_id=item_id,
                data_archive_member=data_member,
                archive_path=item_archive_path,
            ).to_dict(),
            item_id=item_id,
            data_member=data_member,
            name=item_names[item_id],
            type_names=type_names,
            revives_into_species_id=revives_into_by_item.get(item_id),
            berry=berry_by_item.get(item_id),
        )
        for item_id, data_member in enumerate(data_members)
    ]

    envelope = dataset_envelope(
        schema_version=ITEMS_RAW_SCHEMA_VERSION,
        game=profile.id,
        engine=profile.engine,
        dataset="items",
        source=source,
        records=records,
    )
    envelope["public_record_count"] = sum(record["public"] for record in records)
    envelope.update(reference_descriptions)
    return envelope


def _open_archive(
    profile: Any,
    platform: Any,
    filesystem: Any,
    path: str,
    allow_truncated_parameter: str,
) -> Any:
    return platform.archive_cls.from_bytes(
        filesystem.read(path),
        allow_truncated=profile.parameters.get(allow_truncated_parameter, False),
    )


class _CodeBinary:
    """Read the code binary at most once, and only if a section needs it."""

    def __init__(self, platform: Any, image: Any, adapter: Any) -> None:
        self._platform = platform
        self._image = image
        self._compressed = COMPRESSED_CODE_BINARY in adapter.capabilities
        self._data: bytes | None = None

    def read(self) -> bytes:
        if self._data is None:
            self._data = read_code_binary(
                self._platform, self._image, compressed=self._compressed
            )
        return self._data


def _resolve_type_names(
    adapter: Any, messages: Any, type_names_member: int | None
) -> tuple[str, ...]:
    if type_names_member is not None:
        return adapter.items.parse_english_message_archive(
            messages.read(type_names_member)
        )
    # This generation has no ROM text table for type names at all (no
    # new types were added over Generation IV), so Natural Gift type
    # names fall back to the engine's own built-in constant table
    # instead of a ROM-decoded one.
    return adapter.enrich.TYPE_NAMES


def _resolve_item_archive_members(
    engine: ItemConcern,
    code_binary: _CodeBinary,
    item_archive_format: str,
    *,
    item_count: int,
    data_member_count: int,
) -> tuple[tuple[int, ...], dict[str, Any]]:
    if item_archive_format == "arm9-map":
        map_offset, data_members = engine.find_item_archive_members(
            code_binary.read(),
            item_count=item_count,
            data_member_count=data_member_count,
        )
        return data_members, {
            "source": "arm9",
            "offset": map_offset,
            "record_count": len(data_members),
        }
    data_members = tuple(range(data_member_count))
    return data_members, {
        "source": "archive-index",
        "record_count": len(data_members),
    }


def _extract_fossil_revivals(
    profile: Any,
    platform: Any,
    filesystem: Any,
    engine: ItemConcern,
    code_binary: _CodeBinary,
    fossil_format: str,
    *,
    item_count: int,
) -> tuple[dict[int, int], dict[str, Any] | None]:
    fossil_revival_table_offset = profile.parameters.get("fossil_revival_table_offset")
    if fossil_revival_table_offset is not None:
        fossil_revivals = engine.parse_fossil_revival_table(
            code_binary.read(),
            offset=fossil_revival_table_offset,
            count=profile.parameters.get("fossil_revival_count"),
            item_count=item_count,
            species_count=engine.POKEMON_NAME_COUNT,
        )
        return _revives_into_by_item(fossil_revivals), {
            "source": "arm9",
            "offset": fossil_revival_table_offset,
            "record_count": len(fossil_revivals),
        }
    if fossil_format != "script-pattern":
        return {}, None
    # Gen V has no fixed ARM9 table like Gen IV's -- the fossil
    # scientist's own script (`layout.scripts`) picks a species by
    # literally comparing the handed-over item against each real fossil
    # item ID (see gen5/bw/scripts.py's module docstring for the full
    # disassembly and generation-specific validation).
    scripts_path = profile.layout["scripts"]
    archive_options = {}
    if profile.parameters.get("field_archives_allow_incorrect_data_block_size", False):
        archive_options["allow_incorrect_data_block_size"] = True
    if profile.parameters.get("field_archives_allow_trailing_data", False):
        archive_options["allow_trailing_data"] = True
    scripts_archive = platform.archive_cls.from_bytes(
        filesystem.read(scripts_path), **archive_options
    )
    fossil_revival_script_file, fossil_revivals = engine.find_fossil_revival_script(
        scripts_archive.read,
        member_count=len(scripts_archive.members),
        item_count=item_count,
        species_count=engine.POKEMON_NAME_COUNT,
    )
    return _revives_into_by_item(fossil_revivals), {
        "source": "script",
        "archive": scripts_path,
        "member": fossil_revival_script_file,
        "record_count": len(fossil_revivals),
    }


def _revives_into_by_item(fossil_revivals: Any) -> dict[int, int]:
    return {revival.item_id: revival.species_id for revival in fossil_revivals}


def _build_archive_item_record(
    engine: ItemConcern,
    parsed: dict[str, Any],
    *,
    item_id: int,
    data_member: int,
    name: str,
    type_names: tuple[str, ...],
    revives_into_species_id: int | None,
    berry: dict[str, Any] | None,
) -> dict[str, Any]:
    # "???" is the ROM's own name-table sentinel for unused item text slots
    # (seen in Gen5, where item ID always equals its archive member, so
    # Gen4's "member 0 is unused" heuristic alone can't exclude them).
    record = {
        **parsed,
        "name": name,
        "public": item_id > 0 and data_member > 0 and name != "???",
        "revives_into_species_id": revives_into_species_id,
        "berry": berry,
    }

    if "field_pocket_id" in parsed:
        pocket_id = parsed["field_pocket_id"]
        if pocket_id >= len(engine.ITEM_POCKET_NAMES):
            raise DataSourceError(f"Unknown item pocket ID: {pocket_id}")
        record["pocket"] = {
            "id": pocket_id,
            "name": engine.ITEM_POCKET_NAMES[pocket_id],
        }

    if "field_use_function_id" in parsed:
        field_use_id = parsed["field_use_function_id"]
        if field_use_id >= len(engine.ITEM_FIELD_USE_NAMES):
            raise DataSourceError(f"Unknown item field-use function ID: {field_use_id}")
        record["field_use"] = {
            "id": field_use_id,
            "name": engine.ITEM_FIELD_USE_NAMES[field_use_id],
        }

    if "natural_gift_type_id" in parsed:
        record["natural_gift_type"] = _resolve_natural_gift_type(
            engine, parsed["natural_gift_type_id"], type_names
        )
    return record


def _resolve_natural_gift_type(
    engine: ItemConcern, natural_gift_type_id: int, type_names: tuple[str, ...]
) -> dict[str, Any] | None:
    if natural_gift_type_id == engine.NATURAL_GIFT_TYPE_NONE:
        return None
    if natural_gift_type_id >= len(type_names):
        raise DataSourceError(f"Unknown Natural Gift type ID: {natural_gift_type_id}")
    return {
        "id": natural_gift_type_id,
        "name": name_slug(type_names[natural_gift_type_id]),
    }


def _extract_berry_data(
    profile: Any,
    platform: Any,
    filesystem: Any,
    engine: ItemConcern,
) -> tuple[dict[int, dict[str, Any]], dict[str, Any] | None]:
    berry_data_path = profile.layout.get("berry_data")
    if berry_data_path is None:
        return {}, None
    first_berry_item_id = profile.parameters.get("first_berry_item_id")
    if first_berry_item_id is None:
        raise ProfileError(
            f"Profile {profile.id} defines berry_data without first_berry_item_id"
        )
    berry_archive = platform.archive_cls.from_bytes(filesystem.read(berry_data_path))
    berry_by_item: dict[int, dict[str, Any]] = {}
    for index in range(len(berry_archive.members)):
        berry = engine.parse_berry_record(berry_archive.read(index))
        berry_by_item[first_berry_item_id + index] = {
            **asdict(berry),
            "firmness_name": engine.BERRY_FIRMNESS_NAMES.get(berry.firmness),
        }
    return berry_by_item, {
        "archive": berry_data_path,
        "record_count": len(berry_by_item),
    }

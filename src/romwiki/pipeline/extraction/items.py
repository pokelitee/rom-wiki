from __future__ import annotations

from dataclasses import asdict
from typing import Any

from romwiki.engines.registry import get_engine
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
    try:
        item_archive_path = profile.layout["item_data"]
        message_archive_path = profile.layout["messages"]
        item_names_member = profile.parameters["item_names_member"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} is missing item metadata: {error.args[0]}"
        ) from error
    berry_data_path = profile.layout.get("berry_data")
    type_names_member = profile.parameters.get("type_names_member")
    fossil_revival_table_offset = profile.parameters.get("fossil_revival_table_offset")
    fossil_revival_count = profile.parameters.get("fossil_revival_count")
    first_berry_item_id = profile.parameters.get("first_berry_item_id")

    platform = get_platform(profile.platform)
    adapter = get_engine(profile.engine)
    engine = adapter.items
    fossil_format = adapter.formats.fossils
    item_archive_format = adapter.formats.item_archive
    filesystem = platform.filesystem_from_image(result.image)
    item_archive = platform.archive_cls.from_bytes(
        filesystem.read(item_archive_path),
        allow_truncated=profile.parameters.get("items_allow_truncated", False),
    )
    messages = platform.archive_cls.from_bytes(
        filesystem.read(message_archive_path),
        allow_truncated=profile.parameters.get("messages_allow_truncated", False),
    )
    item_names = engine.parse_english_message_archive(messages.read(item_names_member))
    reference_descriptions = extract_reference_descriptions(
        profile, filesystem, messages, fields={"item_descriptions"}
    )

    type_names: tuple[str, ...] = ()
    if type_names_member is not None:
        type_names = engine.parse_english_message_archive(
            messages.read(type_names_member)
        )
    else:
        # This generation has no ROM text table for type names at all (no
        # new types were added over Generation IV), so Natural Gift type
        # names fall back to the engine's own built-in constant table
        # instead of a ROM-decoded one.
        type_names = get_engine(profile.engine).enrich.TYPE_NAMES

    source: dict[str, Any] = {
        "rom_sha256": result.image.hashes.sha256,
        "archive": item_archive_path,
        "item_names": {
            "archive": message_archive_path,
            "member": item_names_member,
        },
    }

    if item_archive_format == "arm9-map":
        arm9_data = read_code_binary(platform, result.image, engine)
        map_offset, data_members = engine.find_item_archive_members(
            arm9_data,
            item_count=len(item_names),
            data_member_count=len(item_archive.members),
        )
        source["item_archive_map"] = {
            "source": "arm9",
            "offset": map_offset,
            "record_count": len(data_members),
        }
    else:
        arm9_data = None
        data_members = tuple(range(len(item_archive.members)))
        source["item_archive_map"] = {
            "source": "archive-index",
            "record_count": len(data_members),
        }

    if type_names_member is not None:
        source["type_names"] = {
            "archive": message_archive_path,
            "member": type_names_member,
        }

    revives_into_by_item: dict[int, int] = {}
    if fossil_revival_table_offset is not None:
        if arm9_data is None:
            arm9_data = read_code_binary(platform, result.image, engine)
        fossil_revivals = engine.parse_fossil_revival_table(
            arm9_data,
            offset=fossil_revival_table_offset,
            count=fossil_revival_count,
            item_count=len(item_names),
            species_count=engine.POKEMON_NAME_COUNT,
        )
        revives_into_by_item = {
            revival.item_id: revival.species_id for revival in fossil_revivals
        }
        source["fossil_revival_table"] = {
            "source": "arm9",
            "offset": fossil_revival_table_offset,
            "record_count": len(fossil_revivals),
        }
    elif fossil_format == "script-pattern":
        # Gen V has no fixed ARM9 table like Gen IV's -- the fossil
        # scientist's own script (`layout.scripts`) picks a species by
        # literally comparing the handed-over item against each real fossil
        # item ID (see gen5/bw/scripts.py's module docstring for the full
        # disassembly and generation-specific validation).
        scripts_path = profile.layout["scripts"]
        archive_options = {}
        if profile.parameters.get(
            "field_archives_allow_incorrect_data_block_size", False
        ):
            archive_options["allow_incorrect_data_block_size"] = True
        if profile.parameters.get("field_archives_allow_trailing_data", False):
            archive_options["allow_trailing_data"] = True
        scripts_archive = platform.archive_cls.from_bytes(
            filesystem.read(scripts_path), **archive_options
        )
        fossil_revival_script_file, fossil_revivals = engine.find_fossil_revival_script(
            scripts_archive.read,
            member_count=len(scripts_archive.members),
            item_count=len(item_names),
            species_count=engine.POKEMON_NAME_COUNT,
        )
        revives_into_by_item = {
            revival.item_id: revival.species_id for revival in fossil_revivals
        }
        source["fossil_revival_table"] = {
            "source": "script",
            "archive": scripts_path,
            "member": fossil_revival_script_file,
            "record_count": len(fossil_revivals),
        }

    berry_by_item: dict[int, dict[str, Any]] = {}
    if berry_data_path is not None:
        berry_by_item = _extract_berry_data(
            profile,
            platform,
            filesystem,
            engine,
            berry_data_path,
            first_berry_item_id,
        )
        source["berry_data"] = {
            "archive": berry_data_path,
            "record_count": len(berry_by_item),
        }

    # "???" is the ROM's own name-table sentinel for unused item text slots
    # (seen in Gen5, where item ID always equals its archive member, so
    # Gen4's "member 0 is unused" heuristic alone can't exclude them).
    records = []
    for item_id, data_member in enumerate(data_members):
        parsed = engine.parse_item_record(
            item_archive.read(data_member),
            item_id=item_id,
            data_archive_member=data_member,
            archive_path=item_archive_path,
        ).to_dict()
        name = item_names[item_id]
        record = {
            **parsed,
            "name": name,
            "public": item_id > 0 and data_member > 0 and name != "???",
            "revives_into_species_id": revives_into_by_item.get(item_id),
            "berry": berry_by_item.get(item_id),
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
                raise DataSourceError(
                    f"Unknown item field-use function ID: {field_use_id}"
                )
            record["field_use"] = {
                "id": field_use_id,
                "name": engine.ITEM_FIELD_USE_NAMES[field_use_id],
            }

        if "natural_gift_type_id" in parsed:
            natural_gift_type_id = parsed["natural_gift_type_id"]
            if (
                natural_gift_type_id != engine.NATURAL_GIFT_TYPE_NONE
                and natural_gift_type_id >= len(type_names)
            ):
                raise DataSourceError(
                    f"Unknown Natural Gift type ID: {natural_gift_type_id}"
                )
            record["natural_gift_type"] = (
                None
                if natural_gift_type_id == engine.NATURAL_GIFT_TYPE_NONE
                else {
                    "id": natural_gift_type_id,
                    "name": name_slug(type_names[natural_gift_type_id]),
                }
            )

        records.append(record)

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


def _extract_berry_data(
    profile: Any,
    platform: Any,
    filesystem: Any,
    engine: Any,
    berry_data_path: str,
    first_berry_item_id: int | None,
) -> dict[int, dict[str, Any]]:
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
    return berry_by_item

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from romwiki.engines.registry import get_engine
from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.pipeline.semantics.location_sections import (
    validate_location_sections,
)
from romwiki.platforms.registry import get_platform
from romwiki.util.errors import ProfileError


@dataclass(frozen=True)
class ArchiveLocationSource:
    profile: Any
    engine: Any
    rom_sha256: str
    map_headers_path: str
    map_names_member: int
    overworld_objects_path: str
    map_matrices_path: str
    scripts_path: str
    messages_path: str
    map_headers: Any
    messages: Any
    headers: tuple[Any, ...]
    script_file_ids: tuple[int, ...]
    overworld_objects: Any
    map_matrices: Any
    scripts: Any
    unused_overworld_members: frozenset[int]


@dataclass(frozen=True)
class ArchiveLocationCatalogs:
    item_names_by_id: dict[int, str]
    item_prices_by_id: dict[int, int | None]
    shops_by_id: dict[int, dict[str, Any]]

    @property
    def item_count(self) -> int:
        return max(self.item_names_by_id, default=-1) + 1


def load_archive_location_source(
    result: InspectionResult,
) -> ArchiveLocationSource:
    assert result.match is not None
    profile = result.match.profile
    try:
        map_headers_path = profile.layout["map_headers"]
        map_names_member = profile.parameters["map_names_member"]
        overworld_objects_path = profile.layout["overworld_objects"]
        map_matrices_path = profile.layout["map_matrices"]
        scripts_path = profile.layout["scripts"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} is missing location metadata: {error.args[0]}"
        ) from error

    platform = get_platform(profile.platform)
    if platform.filesystem_from_image is None or platform.archive_cls is None:
        raise ProfileError(
            f"Platform {profile.platform!r} does not support archive-based extraction"
        )
    engine = get_engine(profile.engine).locations
    filesystem = platform.filesystem_from_image(result.image)
    field_archive_options = {}
    if profile.parameters.get("field_archives_allow_incorrect_data_block_size", False):
        field_archive_options["allow_incorrect_data_block_size"] = True
    if profile.parameters.get("field_archives_allow_trailing_data", False):
        field_archive_options["allow_trailing_data"] = True

    messages_path = profile.layout["messages"]
    map_headers = platform.archive_cls.from_bytes(
        filesystem.read(map_headers_path),
        allow_trailing_data=profile.parameters.get(
            "map_headers_allow_trailing_data", False
        ),
        allow_incorrect_data_block_size=profile.parameters.get(
            "map_headers_allow_incorrect_data_block_size", False
        ),
    )
    messages = platform.archive_cls.from_bytes(filesystem.read(messages_path))
    map_names = engine.parse_english_message_archive(messages.read(map_names_member))
    headers = engine.parse_map_header_table(
        map_headers.read(0),
        map_names=tuple(map_names),
        archive_path=map_headers_path,
    )
    validate_location_sections(
        profile,
        ((header.header_id, header.internal_name) for header in headers),
    )
    script_file_ids = engine.parse_map_header_script_files(map_headers.read(0))
    overworld_objects = platform.archive_cls.from_bytes(
        filesystem.read(overworld_objects_path), **field_archive_options
    )
    map_matrices = platform.archive_cls.from_bytes(filesystem.read(map_matrices_path))
    scripts = platform.archive_cls.from_bytes(
        filesystem.read(scripts_path), **field_archive_options
    )
    return ArchiveLocationSource(
        profile=profile,
        engine=engine,
        rom_sha256=result.image.hashes.sha256,
        map_headers_path=map_headers_path,
        map_names_member=map_names_member,
        overworld_objects_path=overworld_objects_path,
        map_matrices_path=map_matrices_path,
        scripts_path=scripts_path,
        messages_path=messages_path,
        map_headers=map_headers,
        messages=messages,
        headers=headers,
        script_file_ids=script_file_ids,
        overworld_objects=overworld_objects,
        map_matrices=map_matrices,
        scripts=scripts,
        unused_overworld_members=frozenset(
            profile.parameters.get("overworld_objects_unused", ())
        ),
    )


def build_archive_location_catalogs(
    item_dataset: dict[str, Any] | None,
    mart_dataset: dict[str, Any] | None,
) -> ArchiveLocationCatalogs:
    return ArchiveLocationCatalogs(
        item_names_by_id={
            record["item_id"]: record["name"]
            for record in (item_dataset or {}).get("records", ())
        },
        item_prices_by_id={
            record["item_id"]: record.get("price")
            for record in (item_dataset or {}).get("records", ())
        },
        shops_by_id={
            record["shop_id"]: record
            for record in (mart_dataset or {}).get("records", ())
        },
    )

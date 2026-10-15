from __future__ import annotations

from collections.abc import Callable, Collection
from typing import Any

from romwiki.engines.concerns import ReferenceNameConcern
from romwiki.engines.registry import get_engine
from romwiki.platforms.registry import get_platform
from romwiki.profiles.models import GameProfile
from romwiki.util.errors import DataSourceError, ProfileError

_TableCount = Callable[[ReferenceNameConcern], int | None]

# Each table's profile parameter and the engine constant naming its size.
_NAME_TABLES: dict[str, tuple[str, _TableCount]] = {
    "type_names": ("type_names_member", lambda engine: engine.TYPE_NAME_COUNT),
    "ability_names": (
        "ability_names_member",
        lambda engine: engine.ABILITY_NAME_COUNT,
    ),
    "item_names": ("item_names_member", lambda engine: engine.ITEM_NAME_COUNT),
    "move_names": ("move_names_member", lambda engine: engine.MOVE_NAME_COUNT),
    "pokemon_names": (
        "pokemon_names_member",
        lambda engine: engine.POKEMON_NAME_COUNT,
    ),
}

_DESCRIPTION_TABLES: dict[str, tuple[str, _TableCount]] = {
    "ability_descriptions": (
        "ability_descriptions_member",
        lambda engine: engine.ABILITY_NAME_COUNT,
    ),
    "item_descriptions": (
        "item_descriptions_member",
        lambda engine: engine.ITEM_NAME_COUNT,
    ),
    "move_descriptions": (
        "move_descriptions_member",
        lambda engine: engine.MOVE_NAME_COUNT,
    ),
    "pokemon_descriptions": (
        "pokemon_descriptions_member",
        lambda engine: engine.POKEMON_DESCRIPTION_COUNT,
    ),
}


def extract_reference_names(
    profile: GameProfile,
    filesystem: Any,
    message_archive: Any | None = None,
) -> dict[str, Any]:
    engine = get_engine(profile.engine).reference_names
    configured = {
        field: (parameter, count_of(engine))
        for field, (parameter, count_of) in _NAME_TABLES.items()
        if parameter in profile.parameters
    }
    if not configured:
        return {}
    try:
        archive_path = profile.layout["messages"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} defines name tables without a message archive"
        ) from error
    archive_cls = get_platform(profile.platform).archive_cls
    if archive_cls is None:
        raise ProfileError(
            f"Platform {profile.platform!r} does not support archive-based extraction"
        )
    parse_english_message_archive = engine.parse_english_message_archive
    archive_options = {}
    if profile.parameters.get("messages_allow_truncated", False):
        archive_options["allow_truncated"] = True
    archive = message_archive or archive_cls.from_bytes(
        filesystem.read(archive_path), **archive_options
    )
    result: dict[str, Any] = {"name_sources": {}}
    for field, (parameter, expected_count) in configured.items():
        member = profile.int_parameter(parameter)
        names = parse_english_message_archive(archive.read(member))
        if len(names) != expected_count or any(not name for name in names):
            raise DataSourceError(
                f"Expected exactly {expected_count} names in message member {member}"
            )
        result[field] = list(names)
        result["name_sources"][field] = {
            "archive": archive_path,
            "member": member,
        }
    return result


def extract_reference_descriptions(
    profile: GameProfile,
    filesystem: Any,
    message_archive: Any | None = None,
    *,
    fields: Collection[str] | None = None,
) -> dict[str, Any]:
    engine = get_engine(profile.engine).reference_names
    configured = {
        field: (parameter, count_of(engine))
        for field, (parameter, count_of) in _DESCRIPTION_TABLES.items()
        if parameter in profile.parameters and (fields is None or field in fields)
    }
    if not configured:
        return {}
    try:
        archive_path = profile.layout["messages"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} defines description tables without a message archive"
        ) from error
    archive_cls = get_platform(profile.platform).archive_cls
    if archive_cls is None:
        raise ProfileError(
            f"Platform {profile.platform!r} does not support archive-based extraction"
        )
    archive_options = {}
    if profile.parameters.get("messages_allow_truncated", False):
        archive_options["allow_truncated"] = True
    archive = message_archive or archive_cls.from_bytes(
        filesystem.read(archive_path), **archive_options
    )
    result: dict[str, Any] = {"description_sources": {}}
    for field, (parameter, expected_count) in configured.items():
        member = profile.int_parameter(parameter)
        descriptions = engine.parse_english_message_archive(archive.read(member))
        if len(descriptions) != expected_count:
            raise DataSourceError(
                f"Expected exactly {expected_count} descriptions in message member "
                f"{member}"
            )
        result[field] = list(descriptions)
        result["description_sources"][field] = {
            "archive": archive_path,
            "member": member,
        }
    return result

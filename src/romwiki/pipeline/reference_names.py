from __future__ import annotations

from typing import Any

from romwiki.engines.gen4_dppt import parse_english_message_archive
from romwiki.util.errors import DataSourceError, ProfileError
from romwiki.platforms.nds import NarcArchive, NintendoDSFileSystem
from romwiki.profiles.models import GameProfile


_NAME_TABLES = {
    "type_names": ("type_names_member", 18),
    "ability_names": ("ability_names_member", 124),
    "item_names": ("item_names_member", 468),
    "move_names": ("move_names_member", 468),
}


def extract_reference_names(
    profile: GameProfile,
    filesystem: NintendoDSFileSystem,
    message_archive: NarcArchive | None = None,
) -> dict[str, Any]:
    configured = {
        field: (parameter, expected_count)
        for field, (parameter, expected_count) in _NAME_TABLES.items()
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
    archive = message_archive or NarcArchive.from_bytes(filesystem.read(archive_path))
    result: dict[str, Any] = {"name_sources": {}}
    for field, (parameter, expected_count) in configured.items():
        member = profile.parameters[parameter]
        if not isinstance(member, int):
            raise ProfileError(f"Profile {profile.id} has an invalid {parameter}")
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

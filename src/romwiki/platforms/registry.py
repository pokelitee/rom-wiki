from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from romwiki.platforms.nds import (
    NarcArchive,
    NintendoDSFileSystem,
    NintendoDSImage,
    arm9_load_address,
    read_arm9_binary,
    read_arm9_binary_decompressed,
    read_arm9_overlay,
    read_arm9_overlay_decompressed,
)
from romwiki.util.errors import DataSourceError


class RomImage(Protocol):
    """Minimal image surface a profile needs to identify and cache a ROM."""

    hashes: Any

    def to_dict(self) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class PlatformAdapter:
    """Everything a pipeline module needs from one platform's container format."""

    inspect: Callable[[Path], RomImage]
    filesystem_from_image: Callable[[RomImage], Any]
    matches_header: Callable[[RomImage, Sequence[str], Sequence[int]], bool]
    archive_cls: type
    read_overlay: Callable[..., tuple[int, bytes]] | None = None
    read_overlay_decompressed: Callable[..., tuple[int, bytes]] | None = None
    read_code_binary: Callable[[RomImage], bytes] | None = None
    read_decompressed_code_binary: Callable[[RomImage], bytes] | None = None
    code_load_address: Callable[[RomImage], int] | None = None


def _nds_matches_header(
    image: NintendoDSImage, game_codes: Sequence[str], rom_versions: Sequence[int]
) -> bool:
    return (
        image.header.game_code in game_codes
        and image.header.rom_version in rom_versions
    )


_PLATFORMS: dict[str, PlatformAdapter] = {
    "nintendo-ds": PlatformAdapter(
        inspect=NintendoDSImage.inspect,
        filesystem_from_image=NintendoDSFileSystem.from_image,
        matches_header=_nds_matches_header,
        archive_cls=NarcArchive,
        read_overlay=read_arm9_overlay,
        read_overlay_decompressed=read_arm9_overlay_decompressed,
        read_code_binary=read_arm9_binary,
        read_decompressed_code_binary=read_arm9_binary_decompressed,
        code_load_address=arm9_load_address,
    ),
}


def get_platform(platform: str) -> PlatformAdapter:
    try:
        return _PLATFORMS[platform]
    except KeyError as error:
        raise DataSourceError(f"Unsupported platform: {platform!r}") from error


def registered_platforms() -> dict[str, PlatformAdapter]:
    """Return the registered platform adapters keyed by platform ID."""
    return dict(_PLATFORMS)


def register_platform(
    platform: str, adapter: PlatformAdapter, *, validate: bool = True
) -> None:
    """Register a platform adapter under `platform`, replacing any existing entry.

    Intended for tests exercising the extraction contract against a throwaway
    fake platform; real platforms register themselves in `_PLATFORMS` above.
    """
    if validate:
        _validate_platform_adapter(platform, adapter)
    _PLATFORMS[platform] = adapter


def unregister_platform(platform: str) -> None:
    """Remove a previously registered platform, e.g. in a test's tearDown."""
    _PLATFORMS.pop(platform, None)


def _validate_platform_adapter(platform: str, adapter: PlatformAdapter) -> None:
    if not platform or any(character.isspace() for character in platform):
        raise DataSourceError(f"Invalid platform identifier: {platform!r}")
    required_callables = {
        "inspect": adapter.inspect,
        "filesystem_from_image": adapter.filesystem_from_image,
        "matches_header": adapter.matches_header,
    }
    missing = [
        name for name, member in required_callables.items() if not callable(member)
    ]
    if not hasattr(adapter.archive_cls, "from_bytes"):
        missing.append("archive_cls.from_bytes")
    optional_callables = {
        "read_overlay": adapter.read_overlay,
        "read_overlay_decompressed": adapter.read_overlay_decompressed,
        "read_code_binary": adapter.read_code_binary,
        "read_decompressed_code_binary": adapter.read_decompressed_code_binary,
        "code_load_address": adapter.code_load_address,
    }
    invalid_optional = [
        name
        for name, member in optional_callables.items()
        if member is not None and not callable(member)
    ]
    if missing or invalid_optional:
        names = ", ".join((*missing, *invalid_optional))
        raise DataSourceError(
            f"Platform {platform!r} adapter has invalid members: {names}"
        )


for _platform_id, _adapter in _PLATFORMS.items():
    _validate_platform_adapter(_platform_id, _adapter)

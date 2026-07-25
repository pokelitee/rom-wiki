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


def register_platform(platform: str, adapter: PlatformAdapter) -> None:
    """Register a platform adapter under `platform`, replacing any existing entry.

    Intended for tests exercising the extraction contract against a throwaway
    fake platform; real platforms register themselves in `_PLATFORMS` above.
    """
    _PLATFORMS[platform] = adapter


def unregister_platform(platform: str) -> None:
    """Remove a previously registered platform, e.g. in a test's tearDown."""
    _PLATFORMS.pop(platform, None)

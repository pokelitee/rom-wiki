from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from romwiki.platforms.nds import (
    NarcArchive,
    NintendoDSFileSystem,
    NintendoDSImage,
    read_arm9_overlay,
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
    ),
}


def get_platform(platform: str) -> PlatformAdapter:
    try:
        return _PLATFORMS[platform]
    except KeyError as error:
        raise DataSourceError(f"Unsupported platform: {platform!r}") from error

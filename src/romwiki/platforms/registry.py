from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from romwiki.platforms.gba import GbaImage
from romwiki.platforms.gba import read_bytes as gba_read_bytes
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

    @property
    def path(self) -> Path: ...

    @property
    def size(self) -> int: ...

    @property
    def hashes(self) -> Any: ...

    def to_dict(self) -> dict[str, Any]: ...


class ArchiveMember(Protocol):
    """Minimal member surface pipeline extraction code reads by index."""

    @property
    def index(self) -> int: ...


class Archive(Protocol):
    """Minimal container surface a platform's `archive_cls` must provide."""

    @property
    def members(self) -> Sequence[ArchiveMember]: ...

    @classmethod
    def from_bytes(
        cls,
        data: bytes,
        *,
        allow_truncated: bool = False,
        allow_trailing_data: bool = False,
        allow_incorrect_data_block_size: bool = False,
    ) -> Archive: ...

    def read(self, index: int) -> bytes: ...


class OverlayDescriptor(Protocol):
    """Minimal overlay metadata surface `read_overlay*` must return."""

    @property
    def id(self) -> int: ...

    @property
    def file_id(self) -> int: ...


@dataclass(frozen=True, slots=True)
class PlatformAdapter[ImageT: RomImage]:
    """Everything a pipeline module needs from one platform's container format.

    Generic over the platform's own concrete image type: every callable field
    on one adapter instance is always called with that same platform's image
    (`inspect` produces it, the rest consume it), so the type parameter ties
    them together without forcing every platform to share one image shape.
    """

    inspect: Callable[[Path], ImageT]
    matches_header: Callable[[ImageT, Sequence[str], Sequence[int]], bool]
    filesystem_from_image: Callable[[ImageT], Any] | None = None
    archive_cls: type[Archive] | None = None
    read_bytes: Callable[[ImageT, int, int], bytes] | None = None
    read_overlay: Callable[[ImageT, int], tuple[OverlayDescriptor, bytes]] | None = None
    read_overlay_decompressed: (
        Callable[[ImageT, int], tuple[OverlayDescriptor, bytes]] | None
    ) = None
    read_code_binary: Callable[[ImageT], bytes] | None = None
    read_decompressed_code_binary: Callable[[ImageT], bytes] | None = None
    code_load_address: Callable[[ImageT], int] | None = None


def _nds_matches_header(
    image: NintendoDSImage, game_codes: Sequence[str], rom_versions: Sequence[int]
) -> bool:
    return (
        image.header.game_code in game_codes
        and image.header.rom_version in rom_versions
    )


def _gba_matches_header(
    image: GbaImage, game_codes: Sequence[str], rom_versions: Sequence[int]
) -> bool:
    return (
        image.header.game_code in game_codes
        and image.header.software_version in rom_versions
    )


_PLATFORMS: dict[str, PlatformAdapter[Any]] = {
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
    "game-boy-advance": PlatformAdapter(
        inspect=GbaImage.inspect,
        matches_header=_gba_matches_header,
        read_bytes=gba_read_bytes,
    ),
}


def get_platform(platform: str) -> PlatformAdapter[Any]:
    try:
        return _PLATFORMS[platform]
    except KeyError as error:
        raise DataSourceError(f"Unsupported platform: {platform!r}") from error


def registered_platforms() -> dict[str, PlatformAdapter[Any]]:
    """Return the registered platform adapters keyed by platform ID."""
    return dict(_PLATFORMS)


def register_platform(
    platform: str, adapter: PlatformAdapter[Any], *, validate: bool = True
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


def _validate_platform_adapter(platform: str, adapter: PlatformAdapter[Any]) -> None:
    if not platform or any(character.isspace() for character in platform):
        raise DataSourceError(f"Invalid platform identifier: {platform!r}")
    required_callables = {
        "inspect": adapter.inspect,
        "matches_header": adapter.matches_header,
    }
    missing = [
        name for name, member in required_callables.items() if not callable(member)
    ]
    if adapter.archive_cls is None and adapter.read_bytes is None:
        missing.append("archive_cls or read_bytes")
    if adapter.archive_cls is not None and not hasattr(
        adapter.archive_cls, "from_bytes"
    ):
        missing.append("archive_cls.from_bytes")
    optional_callables = {
        "filesystem_from_image": adapter.filesystem_from_image,
        "read_bytes": adapter.read_bytes,
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

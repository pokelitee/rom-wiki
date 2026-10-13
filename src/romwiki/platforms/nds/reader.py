from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from romwiki.platforms.common import RomHashes, calculate_hashes
from romwiki.platforms.nds.blz import decompress_arm9
from romwiki.platforms.nds.header import NintendoDSHeader
from romwiki.util.errors import InvalidRomError

_HEADER_READ_SIZE = 0x200


@dataclass(frozen=True, slots=True)
class NintendoDSImage:
    path: Path
    size: int
    header: NintendoDSHeader
    hashes: RomHashes

    @classmethod
    def inspect(cls, path: Path) -> NintendoDSImage:
        resolved_path = path.expanduser().resolve()
        if not resolved_path.is_file():
            raise InvalidRomError(f"ROM image does not exist: {path}")

        with resolved_path.open("rb") as stream:
            header = NintendoDSHeader.from_bytes(stream.read(_HEADER_READ_SIZE))
            stream.seek(0)
            hashes = calculate_hashes(stream)

        size = resolved_path.stat().st_size
        _validate_regions(header, size)
        return cls(path=resolved_path, size=size, header=header, hashes=hashes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_name": self.path.name,
            "size": self.size,
            "hashes": self.hashes.to_dict(),
            "header": self.header.to_dict(),
        }


def read_arm9_binary(image: NintendoDSImage) -> bytes:
    """Read the full ARM9 code binary from a ROM image."""
    with image.path.open("rb") as stream:
        stream.seek(image.header.arm9_offset)
        return stream.read(image.header.arm9_size)


def read_arm9_binary_decompressed(image: NintendoDSImage) -> bytes:
    """Read the ARM9 binary, BLZ-decompressing it if it's compressed.

    Generation IV's ARM9 is stored raw, so this is a no-op for it; Generation
    V's is BLZ-compressed, so callers that need to byte-pattern-search the
    ARM9 (e.g. the TM/HM move table) should use this instead of
    `read_arm9_binary`.
    """
    return decompress_arm9(read_arm9_binary(image))


def arm9_load_address(image: NintendoDSImage) -> int:
    """Return the RAM address the ARM9 binary is loaded at."""
    return image.header.arm9_ram_address


def _validate_regions(header: NintendoDSHeader, image_size: int) -> None:
    regions = {
        "ARM9": (header.arm9_offset, header.arm9_size),
        "ARM7": (header.arm7_offset, header.arm7_size),
        "file name table": (
            header.file_name_table_offset,
            header.file_name_table_size,
        ),
        "file allocation table": (
            header.file_allocation_table_offset,
            header.file_allocation_table_size,
        ),
    }
    for name, (offset, size) in regions.items():
        if offset + size > image_size:
            raise InvalidRomError(
                f"Nintendo DS {name} extends past the end of the image"
            )

from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from romwiki.platforms.common import RomHashes, calculate_hashes
from romwiki.platforms.gba.header import GbaHeader
from romwiki.util.errors import InvalidRomError

_HEADER_READ_SIZE = 0xC0
# The cartridge ROM address space is 32 MiB, so no GBA image is larger.
_MAX_IMAGE_SIZE = 0x2000000


@dataclass(frozen=True, slots=True)
class GbaImage:
    path: Path
    size: int
    header: GbaHeader
    hashes: RomHashes
    # The whole image: extraction makes tens of thousands of small reads, and
    # reopening the file for each one dominated build time.
    data: bytes = field(repr=False, compare=False)

    @classmethod
    def inspect(cls, path: Path) -> GbaImage:
        resolved_path = path.expanduser().resolve()
        if not resolved_path.is_file():
            raise InvalidRomError(f"ROM image does not exist: {path}")

        size = resolved_path.stat().st_size
        if size < _HEADER_READ_SIZE:
            raise InvalidRomError(
                f"Game Boy Advance image is too small to contain a header: {path}"
            )
        with resolved_path.open("rb") as stream:
            header = GbaHeader.from_bytes(stream.read(_HEADER_READ_SIZE))
            # Checked after the header so another platform's image is
            # rejected for what it is rather than for its size.
            if size > _MAX_IMAGE_SIZE:
                raise InvalidRomError(
                    f"Game Boy Advance image is larger than 32 MiB: {path}"
                )
            stream.seek(0)
            data = stream.read()
        hashes = calculate_hashes(io.BytesIO(data))
        return cls(
            path=resolved_path, size=size, header=header, hashes=hashes, data=data
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_name": self.path.name,
            "size": self.size,
            "hashes": self.hashes.to_dict(),
            "header": self.header.to_dict(),
        }


def read_bytes(image: GbaImage, offset: int, length: int) -> bytes:
    """Read `length` raw bytes starting at `offset` from a flat GBA ROM image."""
    if offset < 0 or length < 0 or offset + length > image.size:
        raise InvalidRomError(
            f"Read of {length} byte(s) at offset {offset:#x} extends past the "
            f"end of {image.path.name} (size {image.size:#x})"
        )
    data = image.data[offset : offset + length]
    if len(data) != length:
        raise InvalidRomError(
            f"Read of {length} byte(s) at offset {offset:#x} from "
            f"{image.path.name} returned only {len(data)} byte(s)"
        )
    return data

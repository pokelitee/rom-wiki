from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from romwiki.platforms.common import RomHashes, calculate_hashes
from romwiki.platforms.gba.header import GbaHeader
from romwiki.util.errors import InvalidRomError

_HEADER_READ_SIZE = 0xC0


@dataclass(frozen=True, slots=True)
class GbaImage:
    path: Path
    size: int
    header: GbaHeader
    hashes: RomHashes

    @classmethod
    def inspect(cls, path: Path) -> GbaImage:
        resolved_path = path.expanduser().resolve()
        if not resolved_path.is_file():
            raise InvalidRomError(f"ROM image does not exist: {path}")

        with resolved_path.open("rb") as stream:
            header = GbaHeader.from_bytes(stream.read(_HEADER_READ_SIZE))
            stream.seek(0)
            hashes = calculate_hashes(stream)

        size = resolved_path.stat().st_size
        if size < _HEADER_READ_SIZE:
            raise InvalidRomError(
                f"Game Boy Advance image is too small to contain a header: {path}"
            )
        return cls(path=resolved_path, size=size, header=header, hashes=hashes)

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
    with image.path.open("rb") as stream:
        stream.seek(offset)
        data = stream.read(length)
    if len(data) != length:
        raise InvalidRomError(
            f"Read of {length} byte(s) at offset {offset:#x} from "
            f"{image.path.name} returned only {len(data)} byte(s)"
        )
    return data

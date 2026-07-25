from __future__ import annotations

import struct
from dataclasses import dataclass

from romwiki.platforms.nds.blz import blz_decompress, is_blz_compressed
from romwiki.platforms.nds.filesystem import NintendoDSFileSystem
from romwiki.platforms.nds.reader import NintendoDSImage
from romwiki.util.errors import InvalidRomError

OVERLAY_RECORD_SIZE = 32


@dataclass(frozen=True, slots=True)
class NintendoDSOverlay:
    id: int
    ram_address: int
    ram_size: int
    bss_size: int
    static_init_start: int
    static_init_end: int
    file_id: int
    compressed_size_and_flags: int


def read_arm9_overlay(
    image: NintendoDSImage, overlay_id: int
) -> tuple[NintendoDSOverlay, bytes]:
    header = image.header
    with image.path.open("rb") as stream:
        stream.seek(header.arm9_overlay_offset)
        table = stream.read(header.arm9_overlay_size)
    if len(table) != header.arm9_overlay_size:
        raise InvalidRomError("Nintendo DS ARM9 overlay table is truncated")
    overlays = parse_overlay_table(table)
    try:
        overlay = next(value for value in overlays if value.id == overlay_id)
    except StopIteration as error:
        raise InvalidRomError(
            f"Nintendo DS ARM9 overlay {overlay_id} does not exist"
        ) from error

    filesystem = NintendoDSFileSystem.from_image(image)
    if not 0 <= overlay.file_id < len(filesystem.files):
        raise InvalidRomError(
            f"Nintendo DS ARM9 overlay {overlay_id} references invalid file ID "
            f"{overlay.file_id}"
        )
    return overlay, filesystem.read(filesystem.files[overlay.file_id])


def read_arm9_overlay_decompressed(
    image: NintendoDSImage, overlay_id: int
) -> tuple[NintendoDSOverlay, bytes]:
    """Like `read_arm9_overlay`, but BLZ-decompresses the overlay first if
    it's compressed (Generation V's overlays, unlike Generation IV's, may be
    -- confirmed against overlay 21's own metadata: `compressed_size_and_flags`
    reports a nonzero compression flag and a compressed size matching the raw
    file length exactly, and BLZ-decompressing it yields exactly `ram_size`
    bytes, not an arbitrary one)."""
    overlay, data = read_arm9_overlay(image, overlay_id)
    if is_blz_compressed(data):
        data = blz_decompress(data)
    return overlay, data


def parse_overlay_table(data: bytes) -> tuple[NintendoDSOverlay, ...]:
    if len(data) % OVERLAY_RECORD_SIZE:
        raise InvalidRomError("Nintendo DS overlay table has an invalid size")
    overlays = tuple(
        NintendoDSOverlay(*values) for values in struct.iter_unpack("<8I", data)
    )
    ids = [overlay.id for overlay in overlays]
    if len(ids) != len(set(ids)):
        raise InvalidRomError("Nintendo DS overlay table contains duplicate IDs")
    return overlays

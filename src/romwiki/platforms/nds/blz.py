from __future__ import annotations

import struct

from romwiki.util.errors import InvalidRomError

# "Bottom LZ" compression, used by some Nintendo DS ARM9 binaries (this
# project's first user is Generation V, whose ARM9 -- unlike Generation IV's
# -- is compressed this way). Ported from CUE's reference `blz.c`, via the
# ROM-hacking community's Java port (`BLZCoder.java`,
# Ajarmar/universal-pokemon-randomizer-zx): no Python implementation of this
# format exists to depend on instead.
_FOOTER_MAGIC = 0xDEC00621
_BLZ_SHIFT = 1
_BLZ_MASK = 0x80
_BLZ_THRESHOLD = 2
_RAW_MAXIM = 0x00FFFFFF


def strip_arm9_footer(data: bytes) -> bytes:
    """Strip trailing 12-byte Nitro footer block(s) some ARM9 binaries carry
    after the code proper, before the BLZ compression header (if any)."""
    while len(data) >= 12 and (
        _read_u32(data, len(data) - 12) == _FOOTER_MAGIC
        or (
            _read_u32(data, len(data) - 12) == 0
            and _read_u32(data, len(data) - 8) == 0
            and _read_u32(data, len(data) - 4) == 0
        )
    ):
        data = data[:-12]
    return data


def is_blz_compressed(data: bytes) -> bool:
    """Detect a BLZ compression header the same way NDSRom.java's `getARM9`
    does: a plausible header-length byte, and an encoded-size field that's
    close enough to the file's own size to not be a false positive."""
    if len(data) < 8:
        return False
    header_len = data[-5]
    if not 0x08 <= header_len <= 0x0B:
        return False
    compressed_size = int.from_bytes(data[-8:-5], "little")
    return len(data) * 9 // 10 < compressed_size < len(data) * 11 // 10


def blz_decompress(data: bytes) -> bytes:
    pak = bytearray(data) + bytearray(3)
    pak_len = len(data)

    inc_len = _read_masked_u32(pak, pak_len - 4)
    if inc_len < 1:
        dec_len = pak_len
        comp_len = 0
        raw_len = dec_len
    else:
        if pak_len < 8:
            raise InvalidRomError("BLZ data has a bad header")
        hdr_len = pak[pak_len - 5]
        if not 0x08 <= hdr_len <= 0x0B:
            raise InvalidRomError("BLZ data has a bad header length")
        if pak_len <= hdr_len:
            raise InvalidRomError("BLZ data has a bad length")
        enc_len = _read_masked_u32(pak, pak_len - 8) & 0x00FFFFFF
        dec_len = pak_len - enc_len
        comp_len = enc_len - hdr_len
        raw_len = dec_len + enc_len + inc_len
        if raw_len > _RAW_MAXIM:
            raise InvalidRomError("BLZ data has a bad decoded length")

    raw = bytearray(raw_len)
    raw[0:dec_len] = pak[0:dec_len]
    p = dec_len
    r = dec_len
    pak_end = dec_len + comp_len
    raw_end = raw_len

    _invert(pak, dec_len, comp_len)

    mask = 0
    flags = 0
    while r < raw_end:
        mask >>= _BLZ_SHIFT
        if mask == 0:
            if p == pak_end:
                break
            flags = pak[p]
            p += 1
            mask = _BLZ_MASK
        if (flags & mask) == 0:
            if p == pak_end:
                break
            raw[r] = pak[p]
            r += 1
            p += 1
        else:
            if p + 1 >= pak_end:
                break
            pos = pak[p] << 8
            p += 1
            pos |= pak[p]
            p += 1
            length = (pos >> 12) + _BLZ_THRESHOLD + 1
            if r + length > raw_end:
                length = raw_end - r
            pos = (pos & 0xFFF) + 3
            for _ in range(length):
                raw[r] = raw[r - pos]
                r += 1

    _invert(raw, dec_len, raw_len - dec_len)
    return bytes(raw[:r])


def decompress_arm9(data: bytes) -> bytes:
    """Strip any trailing footer and BLZ-decompress an ARM9 binary if it's
    compressed; returns the input as-is (footer stripped) otherwise, so it's
    always safe to call regardless of which generation's ARM9 this is."""
    data = strip_arm9_footer(data)
    if is_blz_compressed(data):
        return blz_decompress(data)
    return data


def _read_u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def _read_masked_u32(buf: bytearray, offset: int) -> int:
    return (
        buf[offset]
        | (buf[offset + 1] << 8)
        | (buf[offset + 2] << 16)
        | ((buf[offset + 3] & 0x7F) << 24)
    )


def _invert(buf: bytearray, offset: int, length: int) -> None:
    bottom = offset + length - 1
    while offset < bottom:
        buf[offset], buf[bottom] = buf[bottom], buf[offset]
        offset += 1
        bottom -= 1

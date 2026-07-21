from __future__ import annotations

import struct


def make_script(body: bytes) -> bytes:
    return struct.pack("<iH", 2, 0xFD13) + body


def make_header() -> bytes:
    data = bytearray(0x200)
    data[0:12] = b"POKEMON PL\0\0"
    data[0x0C:0x10] = b"CPUE"
    data[0x10:0x12] = b"01"
    data[0x14] = 10
    data[0x1E] = 1
    struct.pack_into("<I", data, 0x20, 0x4000)
    struct.pack_into("<I", data, 0x28, 0x02000000)
    struct.pack_into("<I", data, 0x2C, 0x100)
    struct.pack_into("<I", data, 0x30, 0x5000)
    struct.pack_into("<I", data, 0x3C, 0x100)
    struct.pack_into("<I", data, 0x40, 0x6000)
    struct.pack_into("<I", data, 0x44, 0x100)
    struct.pack_into("<I", data, 0x48, 0x7000)
    struct.pack_into("<I", data, 0x4C, 0x40)
    struct.pack_into("<I", data, 0x84, 0x4000)
    return bytes(data)


def make_narc() -> bytes:
    raw_data = b"abc\0de"
    fat = struct.pack("<4sII", b"BTAF", 28, 2)
    fat += struct.pack("<IIII", 0, 3, 4, 6)
    fnt = struct.pack("<4sI", b"BTNF", 8)
    image = struct.pack("<4sI", b"GMIF", 8 + len(raw_data)) + raw_data
    file_size = 16 + len(fat) + len(fnt) + len(image)
    header = struct.pack("<4sHHIHH", b"NARC", 0xFFFE, 0x0100, file_size, 16, 3)
    return header + fat + fnt + image

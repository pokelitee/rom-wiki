from __future__ import annotations

from dataclasses import asdict, dataclass
import struct
from typing import Any

from romwiki.errors import InvalidRomError


_MINIMUM_HEADER_SIZE = 0x200


@dataclass(frozen=True, slots=True)
class NintendoDSHeader:
    title: str
    game_code: str
    maker_code: str
    unit_code: int
    device_capacity: int
    rom_version: int
    header_size: int
    arm9_offset: int
    arm9_size: int
    arm7_offset: int
    arm7_size: int
    file_name_table_offset: int
    file_name_table_size: int
    file_allocation_table_offset: int
    file_allocation_table_size: int
    arm9_overlay_offset: int
    arm9_overlay_size: int
    arm7_overlay_offset: int
    arm7_overlay_size: int

    @property
    def declared_capacity_bytes(self) -> int:
        return 128 * 1024 << self.device_capacity

    @property
    def filesystem_file_count(self) -> int:
        return self.file_allocation_table_size // 8

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["declared_capacity_bytes"] = self.declared_capacity_bytes
        result["filesystem_file_count"] = self.filesystem_file_count
        return result

    @classmethod
    def from_bytes(cls, data: bytes) -> NintendoDSHeader:
        if len(data) < _MINIMUM_HEADER_SIZE:
            raise InvalidRomError(
                f"Nintendo DS header requires at least {_MINIMUM_HEADER_SIZE} bytes"
            )

        header = cls(
            title=data[0x00:0x0C].rstrip(b"\0").decode("ascii", errors="replace"),
            game_code=_decode_identifier(data[0x0C:0x10], "game code"),
            maker_code=_decode_identifier(data[0x10:0x12], "maker code"),
            unit_code=data[0x12],
            device_capacity=data[0x14],
            rom_version=data[0x1E],
            header_size=_uint32(data, 0x84),
            arm9_offset=_uint32(data, 0x20),
            arm9_size=_uint32(data, 0x2C),
            arm7_offset=_uint32(data, 0x30),
            arm7_size=_uint32(data, 0x3C),
            file_name_table_offset=_uint32(data, 0x40),
            file_name_table_size=_uint32(data, 0x44),
            file_allocation_table_offset=_uint32(data, 0x48),
            file_allocation_table_size=_uint32(data, 0x4C),
            arm9_overlay_offset=_uint32(data, 0x50),
            arm9_overlay_size=_uint32(data, 0x54),
            arm7_overlay_offset=_uint32(data, 0x58),
            arm7_overlay_size=_uint32(data, 0x5C),
        )
        header._validate()
        return header

    def _validate(self) -> None:
        if self.header_size < _MINIMUM_HEADER_SIZE:
            raise InvalidRomError(f"Invalid Nintendo DS header size: {self.header_size}")
        if self.file_allocation_table_size % 8:
            raise InvalidRomError("Nintendo DS file allocation table has an invalid size")


def _uint32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def _decode_identifier(value: bytes, label: str) -> str:
    try:
        decoded = value.decode("ascii")
    except UnicodeDecodeError as error:
        raise InvalidRomError(f"Nintendo DS {label} is not ASCII") from error
    if not decoded.isalnum():
        raise InvalidRomError(f"Nintendo DS {label} is invalid: {decoded!r}")
    return decoded


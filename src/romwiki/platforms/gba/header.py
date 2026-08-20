from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from romwiki.util.errors import InvalidRomError

_HEADER_SIZE = 0xC0
_FIXED_BYTE_OFFSET = 0xB2
_FIXED_BYTE_VALUE = 0x96
_CHECKSUM_RANGE = (0xA0, 0xBD)
_CHECKSUM_OFFSET = 0xBD
_CHECKSUM_CONSTANT = 0x19


@dataclass(frozen=True, slots=True)
class GbaHeader:
    title: str
    game_code: str
    maker_code: str
    unit_code: int
    device_type: int
    software_version: int
    checksum: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_bytes(cls, data: bytes) -> GbaHeader:
        if len(data) < _HEADER_SIZE:
            raise InvalidRomError(
                f"Game Boy Advance header requires at least {_HEADER_SIZE} bytes"
            )

        fixed_byte = data[_FIXED_BYTE_OFFSET]
        if fixed_byte != _FIXED_BYTE_VALUE:
            raise InvalidRomError(
                f"Game Boy Advance fixed byte is invalid: {fixed_byte:#04x}"
            )

        header = cls(
            title=data[0xA0:0xAC].rstrip(b"\0").decode("ascii", errors="replace"),
            game_code=_decode_identifier(data[0xAC:0xB0], "game code"),
            maker_code=_decode_identifier(data[0xB0:0xB2], "maker code"),
            unit_code=data[0xB3],
            device_type=data[0xB4],
            software_version=data[0xBC],
            checksum=data[_CHECKSUM_OFFSET],
        )
        header._validate(data)
        return header

    def _validate(self, data: bytes) -> None:
        expected = _calculate_checksum(data)
        if self.checksum != expected:
            raise InvalidRomError(
                f"Game Boy Advance header checksum is invalid: "
                f"expected {expected:#04x}, found {self.checksum:#04x}"
            )


def _calculate_checksum(data: bytes) -> int:
    start, end = _CHECKSUM_RANGE
    return (-(sum(data[start:end]) + _CHECKSUM_CONSTANT)) & 0xFF


def _decode_identifier(value: bytes, label: str) -> str:
    try:
        decoded = value.decode("ascii")
    except UnicodeDecodeError as error:
        raise InvalidRomError(f"Game Boy Advance {label} is not ASCII") from error
    if not decoded.isalnum():
        raise InvalidRomError(f"Game Boy Advance {label} is invalid: {decoded!r}")
    return decoded

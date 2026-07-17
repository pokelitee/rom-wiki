from __future__ import annotations

from dataclasses import dataclass
import struct

from romwiki.errors import InvalidRomError


@dataclass(frozen=True, slots=True)
class NarcMember:
    index: int
    start: int
    end: int

    @property
    def size(self) -> int:
        return self.end - self.start


class NarcArchive:
    def __init__(self, data: bytes, members: tuple[NarcMember, ...]) -> None:
        self._data = data
        self.members = members

    @classmethod
    def from_bytes(cls, data: bytes) -> NarcArchive:
        if len(data) < 0x10:
            raise InvalidRomError("NARC archive is too small")
        magic, bom, version, file_size, header_size, block_count = struct.unpack_from(
            "<4sHHIHH", data, 0
        )
        if magic != b"NARC":
            raise InvalidRomError("NARC archive has invalid magic")
        normalized_version = (
            ((version & 0xFF) << 8) | (version >> 8)
            if bom == 0xFFFE
            else version
        )
        if bom not in {0xFEFF, 0xFFFE} or normalized_version != 1:
            raise InvalidRomError("NARC archive has unsupported byte order or version")
        if file_size != len(data):
            raise InvalidRomError("NARC archive size does not match its header")
        if header_size != 0x10 or block_count != 3:
            raise InvalidRomError("NARC archive has an unsupported block layout")

        fat_offset = header_size
        fat_size = _block_size(data, fat_offset, b"BTAF")
        if fat_size < 12:
            raise InvalidRomError("NARC allocation block is too small")
        member_count = struct.unpack_from("<I", data, fat_offset + 8)[0]
        if 12 + member_count * 8 > fat_size:
            raise InvalidRomError("NARC allocation entries are truncated")

        fnt_offset = fat_offset + fat_size
        fnt_size = _block_size(data, fnt_offset, b"BTNF")
        data_block_offset = fnt_offset + fnt_size
        data_block_size = _block_size(data, data_block_offset, b"GMIF")
        if data_block_offset + data_block_size != len(data):
            raise InvalidRomError("NARC blocks do not fill the declared archive")

        raw_data_offset = data_block_offset + 8
        raw_data_size = data_block_size - 8
        members = []
        for index in range(member_count):
            start, end = struct.unpack_from("<II", data, fat_offset + 12 + index * 8)
            if start > end or end > raw_data_size:
                raise InvalidRomError(f"NARC member {index} has invalid bounds")
            members.append(
                NarcMember(
                    index=index,
                    start=raw_data_offset + start,
                    end=raw_data_offset + end,
                )
            )
        return cls(data, tuple(members))

    def read(self, index: int) -> bytes:
        try:
            member = self.members[index]
        except IndexError as error:
            raise InvalidRomError(f"NARC member does not exist: {index}") from error
        return self._data[member.start : member.end]


def _block_size(data: bytes, offset: int, expected_magic: bytes) -> int:
    if offset + 8 > len(data):
        raise InvalidRomError(f"NARC {expected_magic.decode()} block is truncated")
    magic, size = struct.unpack_from("<4sI", data, offset)
    if magic != expected_magic:
        raise InvalidRomError(
            f"Expected NARC block {expected_magic.decode()}, found {magic!r}"
        )
    if size < 8 or offset + size > len(data):
        raise InvalidRomError(f"NARC {expected_magic.decode()} block has invalid size")
    return size

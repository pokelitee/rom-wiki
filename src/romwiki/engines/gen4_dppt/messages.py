from __future__ import annotations

import string
import struct

from romwiki.errors import InvalidRomError


_CHARACTERS = {
    **{0x121 + index: value for index, value in enumerate(string.digits)},
    **{0x12B + index: value for index, value in enumerate(string.ascii_uppercase)},
    **{0x145 + index: value for index, value in enumerate(string.ascii_lowercase)},
    0x188: "é",
    0x1AE: ".",
    0x1B3: "'",
    0x1DE: " ",
}


def parse_english_message_archive(data: bytes) -> tuple[str, ...]:
    if len(data) < 4:
        raise InvalidRomError("Gen IV message archive is too small")
    message_count, archive_key = struct.unpack_from("<HH", data)
    table_end = 4 + message_count * 8
    if table_end > len(data):
        raise InvalidRomError("Gen IV message archive pointer table is truncated")

    messages = []
    for index in range(message_count):
        entry_key = (archive_key * 0x2FD * (index + 1)) & 0xFFFF
        entry_mask = entry_key | entry_key << 16
        offset, length = struct.unpack_from("<II", data, 4 + index * 8)
        offset ^= entry_mask
        length ^= entry_mask
        if offset < table_end or offset + length * 2 > len(data):
            raise InvalidRomError(f"Gen IV message {index} extends outside its archive")
        messages.append(_decode_message(data, offset, length, index))
    return tuple(messages)


def _decode_message(data: bytes, offset: int, length: int, index: int) -> str:
    key = (0x91BD3 * (index + 1)) & 0xFFFF
    characters = []
    for position in range(length):
        value = struct.unpack_from("<H", data, offset + position * 2)[0] ^ key
        key = (key + 0x493D) & 0xFFFF
        if value == 0xFFFF:
            break
        try:
            characters.append(_CHARACTERS[value])
        except KeyError as error:
            raise InvalidRomError(
                f"Unsupported English Gen IV character code: 0x{value:04X}"
            ) from error
    return "".join(characters)

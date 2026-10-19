from __future__ import annotations

import struct

from romwiki.util.errors import InvalidRomError

# Characters 0x100-0x1DE follow pret/pokeplatinum's `tools/msgenc/charmap.txt`,
# except that the fullwidth ampersand and the right single quote decode to
# ASCII, matching the names the other engines produce.
_CHARACTERS = {
    0x100: "○",
    0x101: "□",
    0x102: "△",
    0x103: "◇",
    0x104: "＠",
    0x105: "♫",
    0x106: "％",
    0x107: "☼",
    0x108: "☔",
    0x109: "☰",
    0x10A: "❄",
    0x10B: "☋",
    0x10C: "♔",
    0x10D: "♕",
    0x10E: "☊",
    0x10F: "⇗",
    0x110: "⇘",
    0x111: "☾",
    0x112: "¥",
    0x113: "♈",
    0x114: "♉",
    0x115: "♊",
    0x116: "♋",
    0x117: "♌",
    0x118: "♍",
    0x119: "♎",
    0x11A: "♏",
    0x11B: "←",
    0x11C: "↑",
    0x11D: "↓",
    0x11E: "→",
    0x11F: "‣",
    0x121: "0",
    0x122: "1",
    0x123: "2",
    0x124: "3",
    0x125: "4",
    0x126: "5",
    0x127: "6",
    0x128: "7",
    0x129: "8",
    0x12A: "9",
    0x12B: "A",
    0x12C: "B",
    0x12D: "C",
    0x12E: "D",
    0x12F: "E",
    0x130: "F",
    0x131: "G",
    0x132: "H",
    0x133: "I",
    0x134: "J",
    0x135: "K",
    0x136: "L",
    0x137: "M",
    0x138: "N",
    0x139: "O",
    0x13A: "P",
    0x13B: "Q",
    0x13C: "R",
    0x13D: "S",
    0x13E: "T",
    0x13F: "U",
    0x140: "V",
    0x141: "W",
    0x142: "X",
    0x143: "Y",
    0x144: "Z",
    0x145: "a",
    0x146: "b",
    0x147: "c",
    0x148: "d",
    0x149: "e",
    0x14A: "f",
    0x14B: "g",
    0x14C: "h",
    0x14D: "i",
    0x14E: "j",
    0x14F: "k",
    0x150: "l",
    0x151: "m",
    0x152: "n",
    0x153: "o",
    0x154: "p",
    0x155: "q",
    0x156: "r",
    0x157: "s",
    0x158: "t",
    0x159: "u",
    0x15A: "v",
    0x15B: "w",
    0x15C: "x",
    0x15D: "y",
    0x15E: "z",
    0x15F: "À",
    0x160: "Á",
    0x161: "Â",
    0x162: "Ã",
    0x163: "Ä",
    0x164: "Å",
    0x165: "Æ",
    0x166: "Ç",
    0x167: "È",
    0x168: "É",
    0x169: "Ê",
    0x16A: "Ë",
    0x16B: "Ì",
    0x16C: "Í",
    0x16D: "Î",
    0x16E: "Ï",
    0x16F: "Ð",
    0x170: "Ñ",
    0x171: "Ò",
    0x172: "Ó",
    0x173: "Ô",
    0x174: "Õ",
    0x175: "Ö",
    0x176: "×",
    0x177: "Ø",
    0x178: "Ù",
    0x179: "Ú",
    0x17A: "Û",
    0x17B: "Ü",
    0x17C: "Ý",
    0x17D: "Þ",
    0x17E: "ß",
    0x17F: "à",
    0x180: "á",
    0x181: "â",
    0x182: "ã",
    0x183: "ä",
    0x184: "å",
    0x185: "æ",
    0x186: "ç",
    0x187: "è",
    0x188: "é",
    0x189: "ê",
    0x18A: "ë",
    0x18B: "ì",
    0x18C: "í",
    0x18D: "î",
    0x18E: "ï",
    0x18F: "ð",
    0x190: "ñ",
    0x191: "ò",
    0x192: "ó",
    0x193: "ô",
    0x194: "õ",
    0x195: "ö",
    0x196: "÷",
    0x197: "ø",
    0x198: "ù",
    0x199: "ú",
    0x19A: "û",
    0x19B: "ü",
    0x19C: "ý",
    0x19D: "þ",
    0x19E: "ÿ",
    0x19F: "Œ",
    0x1A0: "œ",
    0x1A1: "Ş",
    0x1A2: "ş",
    0x1A3: "ª",
    0x1A4: "º",
    0x1A5: "¹",
    0x1A6: "²",
    0x1A7: "³",
    0x1A8: "$",
    0x1A9: "¡",
    0x1AA: "¿",
    0x1AB: "!",
    0x1AC: "?",
    0x1AD: ",",
    0x1AE: ".",
    0x1AF: "…",
    0x1B0: "·",
    0x1B1: "/",
    0x1B2: "‘",
    0x1B4: "“",
    0x1B5: "”",
    0x1B6: "„",
    0x1B7: "《",
    0x1B8: "》",
    0x1B9: "(",
    0x1BA: ")",
    0x1BB: "♂",
    0x1BC: "♀",
    0x1BD: "+",
    0x1BE: "-",
    0x1BF: "*",
    0x1C0: "#",
    0x1C1: "=",
    0x1C2: "&",
    0x1C3: "~",
    0x1C4: ":",
    0x1C5: ";",
    0x1C6: "♠",
    0x1C7: "♣",
    0x1C8: "♥",
    0x1C9: "♦",
    0x1CA: "★",
    0x1CB: "◉",
    0x1CC: "●",
    0x1CD: "■",
    0x1CE: "▲",
    0x1CF: "◆",
    0x1D0: "@",
    0x1D1: "♪",
    0x1D2: "%",
    0x1D3: "☀",
    0x1D4: "☁",
    0x1D5: "☂",
    0x1D6: "☃",
    0x1D7: "☺",
    0x1D8: "♚",
    0x1D9: "♛",
    0x1DA: "☹",
    0x1DB: "↗",
    0x1DC: "↘",
    0x1DD: "☽",
    0x120: "&",
    0x1B3: "'",
    0x1DE: " ",
    0x1E0: "Poké",
    0x1E1: "mon",
    # Line, scroll, and page breaks.
    0xE000: "\n",
    0x25BC: "\n",
    0x25BD: "\n",
}


def parse_english_message_archive(
    data: bytes, *, limit: int | None = None
) -> tuple[str, ...]:
    if len(data) < 4:
        raise InvalidRomError("Gen IV message archive is too small")
    message_count, archive_key = struct.unpack_from("<HH", data)
    table_end = 4 + message_count * 8
    if table_end > len(data):
        raise InvalidRomError("Gen IV message archive pointer table is truncated")
    if limit is not None and not 0 <= limit <= message_count:
        raise InvalidRomError("Gen IV message archive limit is out of bounds")

    messages = []
    for index in range(message_count if limit is None else limit):
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
    values = []
    terminated = False
    for position in range(length):
        value = struct.unpack_from("<H", data, offset + position * 2)[0] ^ key
        key = (key + 0x493D) & 0xFFFF
        if value == 0xFFFF:
            terminated = True
            break
        values.append(value)
    if values and values[0] == 0xF100:
        values = _unpack_compressed_characters(
            values[1:], allow_outer_terminator=terminated
        )

    characters = []
    for value in values:
        try:
            characters.append(_CHARACTERS[value])
        except KeyError as error:
            raise InvalidRomError(
                f"Unsupported English Gen IV character code: 0x{value:04X}"
            ) from error
    return "".join(characters)


def _unpack_compressed_characters(
    words: list[int], *, allow_outer_terminator: bool = False
) -> list[int]:
    characters: list[int] = []
    buffer = 0
    bit_count = 0
    for word in words:
        buffer |= word << bit_count
        bit_count += 15
        while bit_count >= 9:
            value = buffer & 0x1FF
            buffer >>= 9
            bit_count -= 9
            if value == 0x1FF:
                return characters
            characters.append(value)
    terminator_prefix = bit_count and buffer == (1 << bit_count) - 1
    if allow_outer_terminator and (bit_count == 0 or terminator_prefix):
        return characters
    raise InvalidRomError("Compressed Gen IV message has no terminator")

from __future__ import annotations

# Generation III's proprietary single-byte character table (the same map
# used by every Gen III game). Verified against the real FireRed and
# LeafGreen ROMs: decoding the move-name table at the offsets in
# `constants.py` against these ranges reproduces every checked move name
# (Pound, Karate Chop, Scratch, Horn Drill, Tackle, Body Slam, Growl,
# Substitute, Struggle, Sketch, Psycho Boost) and the item table's "MASTER
# BALL"/"ULTRA BALL" entries exactly. The period was verified against the
# real region-name table ("MT. MOON", "S.S. ANNE", "SILPH CO.", "CELADON
# DEPT." all decode correctly with it), the other punctuation against the
# species-name table ("FARFETCH'D", "HO-OH", "NIDORAN♀") and trainer names
# ("TATE&LIZA"). Add further entries as they're needed and verified, rather
# than guessing the full table upfront. The apostrophe decodes to ASCII to
# match the names the Nintendo DS engines produce.
_TERMINATOR = 0xFF
_PUNCTUATION = {
    0x00: " ",
    0x2D: "&",
    0xAB: "!",
    0xAC: "?",
    0xAD: ".",
    0xAE: "-",
    0xB4: "'",
    0xB5: "♂",
    0xB6: "♀",
}
_DIGIT_START = 0xA1
_DIGIT_END = 0xAA
_UPPER_START = 0xBB
_UPPER_END = 0xD4
_LOWER_START = 0xD5
_LOWER_END = 0xEE


def decode_gen3_text_table(data: bytes, *, stride: int, count: int) -> list[str]:
    """Decode a flat, fixed-width array of `decode_gen3_text`-encoded strings.

    `data` is the table's own bytes (already sliced from the ROM at the
    table's start offset, sized `stride * count`). The flat-offset
    equivalent of what `pipeline/extraction/reference_names.py` does for NDS
    engines' compressed message archives -- Generation III has no archive/
    message-table concept, so name tables are just a contiguous run of
    fixed-stride entries at a known ROM offset (verified against the real
    move-name table; see `gen3/frlg/moves.py`).
    """
    return [
        decode_gen3_text(data[index * stride : (index + 1) * stride])
        for index in range(count)
    ]


def decode_gen3_text(data: bytes) -> str:
    characters: list[str] = []
    for byte in data:
        if byte == _TERMINATOR:
            break
        if byte in _PUNCTUATION:
            characters.append(_PUNCTUATION[byte])
        elif _DIGIT_START <= byte <= _DIGIT_END:
            characters.append(chr(ord("0") + byte - _DIGIT_START))
        elif _UPPER_START <= byte <= _UPPER_END:
            characters.append(chr(ord("A") + byte - _UPPER_START))
        elif _LOWER_START <= byte <= _LOWER_END:
            characters.append(chr(ord("a") + byte - _LOWER_START))
        else:
            characters.append("?")
    return "".join(characters)

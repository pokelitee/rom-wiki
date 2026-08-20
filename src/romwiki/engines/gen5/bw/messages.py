from __future__ import annotations

import struct

from romwiki.util.errors import InvalidRomError

# Container/decryption/compression algorithm ported from PPTxtHandler.java
# (Ajarmar/universal-pokemon-randomizer-zx), confirmed against a real Black
# ROM's `a/0/0/2` (TextStrings) NARC: decoded Pokémon, ability, move, and item
# names all match known real values exactly (including "Poké Ball"'s accented
# é, U+00E9, confirming the literal-UTF-16 character scheme below).
#
# Unlike Gen4 (fixed archive-wide XOR key), each Gen5 message carries no
# separate key -- it's derived from the message's own terminator and rolled
# backward across the message.
_TERMINATOR = 0xFFFF
_COMPRESSED_MARKER = 0xF100
_HEADER_SIZE = 12

# Runtime-substituted text (e.g. "[RIVAL]'s House"): a 0xF000 marker, a
# variable-ID word, a parameter-count word, then that many parameter words --
# confirmed against a real Black ROM message (map-name table member 89,
# entry 3, an otherwise-unused entry: decodes to two of these sequences
# around a literal "'s " with 1 parameter word each). None of this project's
# currently-decoded name tables (Pokémon/ability/move/item names, or any
# *used* map name) contain one, so the actual variable-ID meanings (what
# gets substituted at runtime) aren't documented here -- this only avoids
# treating the marker/ID/parameter words as literal characters and crashing.
_VARIABLE_MARKER = 0xF000

# A literal line break (documented by the ROM-hacking community's own text
# format notes; not previously handled here, so any message containing one
# crashed). Verified against real Black ROM text: member 53 (item
# descriptions, identified by decoding Potion's own entry, index 17, to its
# exact real text) contains many multi-line descriptions using this code,
# e.g. Cheri Berry's real description ("If held by a Pokémon, \nit recovers
# from paralysis.") decodes cleanly once this is treated as `\n` rather than
# rejected.
_LINE_BREAK = 0xFFFE

# A fixed two-word marker with no varying payload -- confirmed against real
# Black and Black 2 trainer-class tables (member `trainer_classes_member`):
# every occurrence is this exact pair, always the first two words of the
# message, always immediately followed by a plain occupational word
# ("Trainer", "Breeder", "Ranger") with nothing else distinguishing the
# entries that carry it from ones that don't. Previously decoded as two
# literal characters via the generic `chr()` fallback below, producing
# garbage glyphs (U+2486, U+2487) in front of otherwise-ordinary class names
# like "Trainer" -- including several real rival classes (BW's Cheren/Bianca,
# B2W2's PWT roster). Since nothing in this codebase renders in-game icon
# graphics, and no parameter here has ever been observed to vary, the pair
# is dropped rather than guessed at.
_CLASS_ICON_MARKER = (0x2486, 0x2487)

# A single-word marker taking one of exactly two observed values -- confirmed
# against real Black, Black 2, and Blaze Black 2 Redux trainer-class tables:
# "Clerk" and "Swimmer" each appear twice, once with each value, and nothing
# else in this codebase's decoded tables ever uses either value. That paired
# shape (one class, two otherwise-identical entries differing only in this
# marker) matches a male/female icon selector, the same role `_CLASS_ICON_MARKER`
# fills with a fixed pair instead of a choice of one; dropped for the same
# reason -- nothing here renders in-game icon graphics.
_CLASS_GENDER_ICON_MARKERS = frozenset({0x246D, 0x246E})


def parse_english_message_archive(
    data: bytes, *, limit: int | None = None
) -> tuple[str, ...]:
    if len(data) < _HEADER_SIZE:
        raise InvalidRomError("Gen V message archive is too small")
    section_count, message_count = struct.unpack_from("<HH", data, 0)
    if section_count < 1:
        raise InvalidRomError("Gen V message archive has no sections")
    if limit is not None and not 0 <= limit <= message_count:
        raise InvalidRomError("Gen V message archive limit is out of bounds")
    count = message_count if limit is None else limit

    section_offsets_size = section_count * 4
    if _HEADER_SIZE + section_offsets_size > len(data):
        raise InvalidRomError("Gen V message archive section offsets are truncated")
    base = struct.unpack_from("<I", data, _HEADER_SIZE)[0]
    if base + 4 > len(data):
        raise InvalidRomError("Gen V message archive section is out of bounds")

    table_start = base + 4
    table_end = table_start + message_count * 8
    if table_end > len(data):
        raise InvalidRomError("Gen V message archive pointer table is truncated")

    messages = []
    for index in range(count):
        offset, char_count, _unknown = struct.unpack_from(
            "<IHH", data, table_start + index * 8
        )
        message_start = base + offset
        message_end = message_start + char_count * 2
        if message_start < table_end or message_end > len(data):
            raise InvalidRomError(f"Gen V message {index} extends outside its archive")
        words = list(struct.unpack_from(f"<{char_count}H", data, message_start))
        messages.append(_decode_message(words, index))
    return tuple(messages)


def _decode_message(words: list[int], index: int) -> str:
    if not words:
        raise InvalidRomError(f"Gen V message {index} is empty")
    key = words[-1] ^ _TERMINATOR
    for position in range(len(words) - 1, -1, -1):
        words[position] ^= key
        key = ((key >> 3) | (key << 13)) & 0xFFFF

    if words[0] == _COMPRESSED_MARKER:
        # The 9-bit bitstream terminates internally (see below); it never
        # contains the outer 0xFFFF sentinel the uncompressed path checks for.
        code_points = _unpack_compressed_characters(words, index)
    else:
        code_points = []
        for value in words:
            if value == _TERMINATOR:
                break
            code_points.append(value)
        else:
            raise InvalidRomError(f"Gen V message {index} has no terminator")

    characters = []
    position = 0
    while position < len(code_points):
        value = code_points[position]
        if value == _VARIABLE_MARKER:
            if position + 2 >= len(code_points):
                raise InvalidRomError(
                    f"Gen V message {index} has a truncated variable code"
                )
            variable_id = code_points[position + 1]
            param_count = code_points[position + 2]
            params_end = position + 3 + param_count
            if params_end > len(code_points):
                raise InvalidRomError(
                    f"Gen V message {index} has a truncated variable code"
                )
            characters.append(f"{{VAR:{variable_id:04X}}}")
            position = params_end
            continue
        if value == _LINE_BREAK:
            characters.append("\n")
            position += 1
            continue
        if (
            value == _CLASS_ICON_MARKER[0]
            and position + 1 < len(code_points)
            and code_points[position + 1] == _CLASS_ICON_MARKER[1]
        ):
            position += 2
            continue
        if value in _CLASS_GENDER_ICON_MARKERS:
            position += 1
            continue
        if not 20 < value <= 0xFFF0:
            raise InvalidRomError(
                f"Unsupported Gen V character code {value:#06x} in message {index}"
            )
        characters.append(chr(value))
        position += 1
    return "".join(characters)


def _unpack_compressed_characters(words: list[int], index: int) -> list[int]:
    # 9-bits-per-character bitstream packed across 16-bit words, skipping the
    # leading 0xF100 marker. Ported from PPTxtHandler.decompress() (Ajarmar/
    # universal-pokemon-randomizer-zx): unlike Gen4's variant (15 usable
    # bits/word), Gen5 packs all 16 bits/word. Not exercised by any real
    # message in the tables this engine currently decodes (Pokémon/ability/
    # move/item names) -- only covered by a synthetic unit test, so treat the
    # termination/filtering rules below (a 9-bit value whose low byte is 0xFF
    # ends the stream; decoded values 0 and 1 are dropped rather than
    # emitted) as carried over from the reference implementation rather than
    # independently verified against real Gen5 data.
    bits = 0
    bit_count = 0
    unpacked: list[int] = []
    for word in words[1:]:
        bits |= word << bit_count
        bit_count += 16
        while bit_count >= 9:
            value = bits & 0x1FF
            bits >>= 9
            bit_count -= 9
            if (value & 0xFF) == 0xFF:
                return unpacked
            if value not in (0, 1):
                unpacked.append(value)
    # Unreachable for any message read via parse_english_message_archive: the
    # decrypt loop above always forces the last raw code unit to decode to
    # 0xFFFF (an all-1-bits word), which is guaranteed to eventually produce a
    # terminating 9-bit chunk once its bits enter the stream. Kept as a
    # defensive fallback rather than asserted away, in case that guarantee
    # doesn't hold for some real archive this decoder hasn't seen yet.
    raise InvalidRomError(f"Gen V compressed message {index} has no terminator")

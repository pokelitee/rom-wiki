from __future__ import annotations

import struct
from dataclasses import dataclass

from romwiki.util.errors import InvalidRomError

from .constants import NATURE_NAMES
from .scripts import parse_script_table

NPC_TRADE_RECORD_SIZE = 80
INIT_NPC_TRADE = 0x0226
START_NPC_TRADE = 0x0229
FINISH_NPC_TRADE = 0x022A
_NPC_TRADE_SEQUENCE_LIMIT = 64


@dataclass(frozen=True, slots=True)
class Gen4NpcTrade:
    offered_species_id: int
    requested_species_id: int
    ivs: tuple[int, ...]
    ot_id: int
    personality: int
    nature: str
    held_item_id: int | None
    ot_gender: int
    language_id: int
    # Undecoded engine values at record offsets 0x1C, 0x24-0x34, and 0x44,
    # kept raw so hack edits stay auditable until their meaning is verified.
    unknown_values: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class Gen4NpcTradeCommand:
    offset: int
    trade_id: int


def parse_npc_trade_record(
    data: bytes, *, species_count: int, item_count: int
) -> Gen4NpcTrade:
    if len(data) != NPC_TRADE_RECORD_SIZE:
        raise InvalidRomError(
            f"Expected {NPC_TRADE_RECORD_SIZE} bytes for an NPC trade, got {len(data)}"
        )

    offered_species_id = struct.unpack_from("<I", data, 0)[0]
    raw_ivs = struct.unpack_from("<6I", data, 4)
    ivs = raw_ivs[:3] + raw_ivs[4:] + raw_ivs[3:4]
    ot_id = struct.unpack_from("<H", data, 0x20)[0]
    padding = struct.unpack_from("<H", data, 0x22)[0]
    if padding:
        raise InvalidRomError(f"NPC trade has nonzero padding: {padding}")
    unknown_values = (
        struct.unpack_from("<I", data, 0x1C)[0],
        *struct.unpack_from("<5I", data, 0x24),
        struct.unpack_from("<I", data, 0x44)[0],
    )
    personality = struct.unpack_from("<I", data, 0x38)[0]
    raw_held_item_id = struct.unpack_from("<I", data, 0x3C)[0]
    ot_gender = struct.unpack_from("<I", data, 0x40)[0]
    language_id = struct.unpack_from("<I", data, 0x48)[0]
    requested_species_id = struct.unpack_from("<I", data, 0x4C)[0]

    if not 0 < offered_species_id < species_count:
        raise InvalidRomError(
            f"NPC trade references invalid offered species {offered_species_id}"
        )
    if not 0 < requested_species_id < species_count:
        raise InvalidRomError(
            f"NPC trade references invalid requested species {requested_species_id}"
        )
    if any(iv > 31 for iv in ivs):
        raise InvalidRomError("NPC trade contains an invalid IV")
    if raw_held_item_id >= item_count:
        raise InvalidRomError(
            f"NPC trade references invalid held item {raw_held_item_id}"
        )
    if ot_gender not in {0, 1}:
        raise InvalidRomError(f"NPC trade has invalid OT gender {ot_gender}")
    return Gen4NpcTrade(
        offered_species_id=offered_species_id,
        requested_species_id=requested_species_id,
        ivs=ivs,
        ot_id=ot_id,
        personality=personality,
        nature=NATURE_NAMES[personality % len(NATURE_NAMES)],
        held_item_id=raw_held_item_id or None,
        ot_gender=ot_gender,
        language_id=language_id,
        unknown_values=unknown_values,
    )


def parse_npc_trade_commands(
    data: bytes, *, trade_count: int
) -> tuple[Gen4NpcTradeCommand, ...]:
    """Find literal NPC trade initializers used by complete trade sequences."""
    code_offset = parse_script_table(data)
    signature = struct.pack("<H", INIT_NPC_TRADE)
    requested_species_signature = struct.pack("<H", 0x0228)
    start_signature = struct.pack("<H", START_NPC_TRADE)
    finish_signature = struct.pack("<H", FINISH_NPC_TRADE)
    commands = []

    for offset in range(code_offset, len(data) - 2):
        if data[offset : offset + 2] != signature:
            continue
        trade_id = data[offset + 2]
        if trade_id >= trade_count:
            continue

        sequence_start = offset + 3
        sequence_end = min(len(data), sequence_start + _NPC_TRADE_SEQUENCE_LIMIT)
        start_offset = data.find(start_signature, sequence_start, sequence_end)
        if start_offset < 0:
            continue
        requested_species_offset = data.find(
            requested_species_signature, sequence_start, start_offset
        )
        if requested_species_offset < 0:
            continue
        if data[start_offset + 4 : start_offset + 6] != finish_signature:
            continue
        commands.append(Gen4NpcTradeCommand(offset=offset, trade_id=trade_id))
    return tuple(commands)

from __future__ import annotations

import struct
from collections.abc import Sequence

from romwiki.engines.gen4.shared.events import (
    HIDDEN_ITEM_EVENT_TYPE,
    HIDDEN_ITEM_SCRIPT_BASE,
    VISIBLE_ITEM_SCRIPT_BASE,
    Gen4BackgroundEvent,
    Gen4ObjectEvent,
)
from romwiki.engines.gen4.shared.events import (
    is_hidden_item_candidate as is_hidden_item_candidate,
)
from romwiki.engines.gen4.shared.events import (
    is_visible_item_candidate as is_visible_item_candidate,
)
from romwiki.engines.gen4.shared.script_disassembler import disassemble_function
from romwiki.engines.gen4.shared.script_table import parse_script_function_offsets
from romwiki.util.errors import InvalidRomError

# Unlike Platinum, HGSS's item-ball placements do not store the item ID as a
# flat `script_id - 7000` literal. `script_id` instead selects one of 256
# functions in one shared script member (a constant across all four HGSS-
# family ROMs checked -- retail HeartGold, SoulSilver, and the hacks Sacred
# Gold/Storm Silver all have this exact member at index 141, identical size)
# via the field engine's own `sScriptBankMapping`/`_std_item_ball` threshold
# (confirmed against `pret/pokeheartgold`'s public decompilation,
# `src/script_manager.c`). Each function stages a literal item ID and
# quantity into two scratch variables before falling through to one shared
# give-item tail. This table is NOT an identity mapping in retail HGSS --
# cross-checked function-by-function against `pret/pokeheartgold`'s own
# `std_itemball_*` naming constants (e.g. function 0 is
# `std_itemball_r29_potion` and decodes to item 17/Potion here; function 4 is
# `std_itemball_r31_poke_ball` and decodes to item 4/Poké Ball), matched
# exactly for the first nine functions checked. The flat `script_id - 7000`
# shortcut this replaced had therefore been silently resolving the large
# majority of item-ball placements to the wrong item across every HGSS-family
# profile, including unmodified retail HeartGold/SoulSilver, not just the
# hacks -- undetected until this table was decoded and compared against it
# directly. Sacred Gold/Storm Silver additionally repurpose specific table
# entries for hack-added items (e.g. function 44 gives item 433, Woodland
# Ore), which were affected the same way. Verified against real ROM data: all
# five of Sacred Gold's documented "Ore"/"Orb" items are real item-ball
# placements whose table entry gives the documented item, at map locations
# matching `.local/docs/SSSG/Important Item Locations.pdf` exactly (Ilex
# Forest, Ruins of Alph, Route 27, Route 42).
ITEM_BALL_TABLE_SCRIPT_MEMBER = 141
_ITEM_WORK_VARIABLE = 32776
_QUANTITY_WORK_VARIABLE = 32777


def parse_item_ball_table(data: bytes) -> tuple[int | None, ...]:
    """Decode HGSS's shared item-ball table into item literals by function index."""
    entries: list[int | None] = []
    for function_offset in parse_script_function_offsets(data):
        instructions = sorted(
            disassemble_function(data, function_offset).values(),
            key=lambda value: value.offset,
        )
        item_id = None
        for instruction in instructions[:4]:
            if (
                instruction.name == "SetVarFromVar"
                and instruction.params[0] == _ITEM_WORK_VARIABLE
            ):
                item_id = instruction.params[1]
                break
        entries.append(item_id)
    return tuple(entries)


def resolve_visible_item_id(
    event: Gen4ObjectEvent,
    *,
    item_count: int,
    item_ids: Sequence[int | None],
) -> int | None:
    """Resolve a field object to the item its item-ball table entry gives."""
    index = event.script_id - VISIBLE_ITEM_SCRIPT_BASE
    if not 0 <= index < len(item_ids):
        return None
    item_id = item_ids[index]
    return item_id if item_id is not None and 0 < item_id < item_count else None


# Hidden items are a *different* mechanism from item balls, not a variant of
# the same one: they are never dispatched to a per-index field-script
# function at all. `script_manager.c`'s `sScriptBankMapping` entry for
# `_std_hidden_item` (8000) still loads a shared script bank (member 145),
# but that bank compiles down to a single physical function reused for every
# hidden item (confirmed: `parse_script_function_offsets` on member 145
# returns 256 entries that all resolve to the same offset -- a real,
# deliberate collapse, not a decode bug). That one function is a generic
# "wait, stage vars, give item" tail reading three scratch variables
# (32768-32770) it never sets itself.
#
# What actually supplies those three variables, and therefore which item a
# given hidden item gives, is `GetHiddenItemParams` in `script_manager.c`: a
# native ARM9 data table, `sHiddenItemParam`, of fixed 8-byte records
# (`u16 itemId, u8 quantity, u8 unk3, u16 unk4, u16 index`) searched
# *linearly by its own `index` field* -- the table's on-disk order does not
# match `index` order. `HiddenItemScriptNoToHiddenItemIdx` computes
# `index = script_id - 8000`, i.e. the same kind of index item balls use, but
# looked up in a native table instead of a script member.
#
# Located by signature (the table's own index-0 and index-1 records, both
# stable across every HGSS-family ROM checked -- retail HeartGold/SoulSilver
# and the hacks Sacred Gold/Storm Silver all start identically, since neither
# hack edits hidden items the way they edit item balls) rather than a
# per-profile offset, then decoded until a record fails basic validity
# (item ID in range, quantity in 1-99, `unk3 == 0` as every real record has).
# Verified against real ROM data both ways: cross-checked all 231 real
# HeartGold records against `pret/pokeheartgold`'s own decompiled
# `sHiddenItemParam` (`src/data/fieldmap/hidden_items.h`) with zero
# mismatches, and confirmed Sacred Gold's table is byte-for-byte identical to
# retail's at the same ARM9 offset (231 records, indices forming a complete
# 0..230 permutation) -- this hack only edits the item-ball table, not this
# one.
HIDDEN_ITEM_TABLE_RECORD = struct.Struct("<HBBHH")
_HIDDEN_ITEM_TABLE_SIGNATURE = HIDDEN_ITEM_TABLE_RECORD.pack(
    17, 1, 0, 0, 0
) + HIDDEN_ITEM_TABLE_RECORD.pack(92, 1, 0, 0, 1)


def parse_hidden_item_table(
    arm9_data: bytes, *, item_count: int
) -> tuple[int | None, ...]:
    """Decode HGSS's native hidden-item table (`sHiddenItemParam`) by index."""
    offset = arm9_data.find(_HIDDEN_ITEM_TABLE_SIGNATURE)
    if offset < 0:
        raise InvalidRomError("HGSS hidden-item table signature not found")
    entries: dict[int, int] = {}
    position = offset
    while position + HIDDEN_ITEM_TABLE_RECORD.size <= len(arm9_data):
        item_id, quantity, unk3, _unk4, index = HIDDEN_ITEM_TABLE_RECORD.unpack_from(
            arm9_data, position
        )
        if not (0 < item_id < item_count and 0 < quantity <= 99 and unk3 == 0):
            break
        if index in entries:
            raise InvalidRomError(f"HGSS hidden-item table repeats index {index}")
        entries[index] = item_id
        position += HIDDEN_ITEM_TABLE_RECORD.size
    if not entries or sorted(entries) != list(range(len(entries))):
        raise InvalidRomError(
            "HGSS hidden-item table indices are not a dense 0-based range"
        )
    return tuple(entries[index] for index in range(len(entries)))


def resolve_hidden_item_id(
    event: Gen4BackgroundEvent,
    *,
    item_count: int,
    item_ids: Sequence[int | None],
) -> int | None:
    """Resolve a background event to the item its hidden-item table entry gives."""
    if event.event_type != HIDDEN_ITEM_EVENT_TYPE:
        return None
    index = event.script_id - HIDDEN_ITEM_SCRIPT_BASE
    if not 0 <= index < len(item_ids):
        return None
    item_id = item_ids[index]
    return item_id if item_id is not None and 0 < item_id < item_count else None


__all__ = [
    "HIDDEN_ITEM_TABLE_RECORD",
    "ITEM_BALL_TABLE_SCRIPT_MEMBER",
    "is_hidden_item_candidate",
    "is_visible_item_candidate",
    "parse_hidden_item_table",
    "parse_item_ball_table",
    "resolve_hidden_item_id",
    "resolve_visible_item_id",
]

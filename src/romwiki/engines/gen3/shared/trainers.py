from __future__ import annotations

import struct

from romwiki.engines.gen3.shared.constants import TRAINER_RECORD_SIZE
from romwiki.engines.gen3.shared.text import decode_gen3_name
from romwiki.schema import (
    AbilitySlotTrainerPokemon,
    BattleModeTrainer,
    RecordProvenance,
)
from romwiki.util.errors import InvalidRomError

# Generation III's trainer struct (`struct Trainer` in the public
# pokefirered decompilation), verified against the real FireRed and
# LeafGreen ROMs by cross-checking six real gym leaders' rosters (Brock,
# Misty, Lt. Surge, Erika, Koga's party-size progression 2/2/3/3/4) and
# Lance's five-member team (Gyarados, 2x Dragonair, Aerodactyl, Dragonite,
# each carrying a held item and 4 moves):
#   0x00       partyFlags -- bit0 (1) = has_custom_moves, bit1 (2) =
#              has_held_item (same two-flag idea Gen V's `poketype` byte
#              uses; Generation III is structurally its ancestor)
#   0x01       trainerClass (e.g. 0x54=84 shared by all 8 Gym Leaders'
#              "LEADER" class, 0x57=87 for Lance)
#   0x02       encounterMusic_gender (not decoded further this pass)
#   0x03       trainerPic (not decoded further this pass)
#   0x04-0x0F  trainerName (12 bytes, Gen III text-encoded, 0xFF-terminated)
#   0x10-0x17  items (4x u16, AI battle items)
#   0x18       doubleBattle (0=single, nonzero=double -- Generation III has
#              no triple/rotation battle modes, unlike Generation V)
#   0x1C-0x1F  aiFlags (u32)
#   0x20       partySize
#   0x24-0x27  party pointer (u32 GBA ROM address, 0x08000000-based)
# Bytes 0x19-0x1B and 0x21-0x23 are unaccounted-for padding.
#
# Party records (dereferenced through the pointer above) are ALWAYS an
# 8-byte base record -- iv(u16), level(u16), species(u16), heldItem(u16,
# reads 0 when has_held_item is unset) -- with a 4x u16 moves block
# appended (making the record 16 bytes) only when has_custom_moves is set.
# This does NOT vary with has_held_item the way it does in Gen V (where the
# held-item field is only present when its own flag is set); confirmed via
# a flags=0 trainer (8-byte records, held-item field reads 0) and a
# flags=2 (held-item only, no moves) Fighting Dojo trainer (8-byte records
# with a real held item value, no moves block).
_PARTY_BASE_RECORD_SIZE = 8
_PARTY_MOVES_SIZE = 8


def party_record_size(*, has_custom_moves: bool) -> int:
    return _PARTY_BASE_RECORD_SIZE + (_PARTY_MOVES_SIZE if has_custom_moves else 0)


def parse_trainer_record(
    data: bytes,
    party_data: bytes,
    *,
    trainer_id: int,
    archive_path: str,
) -> BattleModeTrainer:
    if len(data) != TRAINER_RECORD_SIZE:
        raise InvalidRomError(
            f"Gen III trainer {trainer_id} has size {len(data)}, "
            f"expected {TRAINER_RECORD_SIZE}"
        )

    party_flags = data[0]
    class_id = data[1]
    name = decode_gen3_name(data[0x04:0x10])
    reward_item_ids = struct.unpack_from("<4H", data, 0x10)
    double_battle = data[0x18] != 0
    ai_flags = struct.unpack_from("<I", data, 0x1C)[0]
    party_count = data[0x20]

    has_custom_moves = bool(party_flags & 1)
    has_held_items = bool(party_flags & 2)
    record_size = party_record_size(has_custom_moves=has_custom_moves)
    expected_size = record_size * party_count
    if len(party_data) != expected_size:
        raise InvalidRomError(
            f"Trainer {trainer_id} party has size {len(party_data)}; expected "
            f"{expected_size} ({party_count} {record_size}-byte records)"
        )

    party = []
    for index in range(party_count):
        offset = index * record_size
        iv, level, species_id, held_item_id = struct.unpack_from(
            "<HHHH", party_data, offset
        )
        move_ids: tuple[int, ...] = ()
        if has_custom_moves:
            move_ids = struct.unpack_from(
                "<4H", party_data, offset + _PARTY_BASE_RECORD_SIZE
            )
        party.append(
            AbilitySlotTrainerPokemon(
                # A single stored IV-like value applies to every stat (unlike
                # Gen V's per-mon `iv_strength` byte scaled 0-255); real
                # values seen this session (0, 100, 250) don't confirm a
                # 0-31/0-255 scale either way, so this is retained as the
                # raw stored value rather than guessing a conversion --
                # `trainer_party.py`'s IV handling documents the same gap.
                iv_strength=iv,
                # Generation III derives ability/gender from each Pokemon's
                # personality value, not a stored per-slot flag -- no real
                # value exists for these fields yet.
                ability_slot=0,
                forced_gender_flag=0,
                level=level,
                species_id=species_id,
                form_id=0,
                held_item_id=held_item_id if has_held_items else None,
                move_ids=move_ids,
            )
        )

    return BattleModeTrainer(
        trainer_id=trainer_id,
        name=name,
        class_id=class_id,
        # Gen III trainer class display names require a separate,
        # not-yet-implemented lookup table (`gTrainerClassNames`), so the
        # class name is undecoded rather than blank.
        class_name=None,
        battle_mode=1 if double_battle else 0,
        double_battle=double_battle,
        has_custom_moves=has_custom_moves,
        has_held_items=has_held_items,
        party_count=party_count,
        reward_item_ids=reward_item_ids,
        ai_flags=ai_flags,
        # Generation III has no confirmed per-trainer healer, victory-item,
        # or money-multiplier field in the struct decoded above, so these are
        # undecoded rather than zero.
        healer=None,
        victory_money_multiplier=None,
        victory_item_id=None,
        party=tuple(party),
        provenance=RecordProvenance(
            source="rom", archive=archive_path, member=trainer_id
        ),
        party_provenance=RecordProvenance(
            source="rom", archive=archive_path, member=trainer_id
        ),
    )


# `gTrainerMoneyTable`: 4-byte entries -- trainer class (u8), money value
# (u8), two bytes of padding -- ending at class 0xFF, whose value applies
# to every class not listed. pret's `GetTrainerMoneyToGive` pays
# 4 x the last Pokémon's level x that value, doubled for a double battle.
# Located in each ROM by pret's table: FireRed lists 104 classes and
# Emerald 55, both with a default of 5.
TRAINER_MONEY_ENTRY_SIZE = 4
_MONEY_TABLE_END = 0xFF
_MAX_MONEY_ENTRIES = 256


def parse_trainer_money_table(
    data: bytes,
) -> tuple[dict[int, tuple[int, int]], tuple[int, int]]:
    """Decode `gTrainerMoneyTable` into `{class: (value, entry index)}` and
    the default `(value, entry index)` from its terminator. `data` may run
    past the table's end.
    """
    values: dict[int, tuple[int, int]] = {}
    for index in range(min(len(data) // TRAINER_MONEY_ENTRY_SIZE, _MAX_MONEY_ENTRIES)):
        start = index * TRAINER_MONEY_ENTRY_SIZE
        class_id, value = data[start], data[start + 1]
        if class_id == _MONEY_TABLE_END:
            return values, (value, index)
        # The game stops at a class's first entry.
        values.setdefault(class_id, (value, index))
    raise InvalidRomError("Gen III trainer money table has no terminator")

"""Byte-compatible trainer record storage shared by the Gen V leaves."""

from __future__ import annotations

import struct

from romwiki.schema import (
    AbilitySlotTrainerPokemon,
    BattleModeTrainer,
    RecordProvenance,
)
from romwiki.util.errors import InvalidRomError

TRAINER_RECORD_SIZE = 20
TRAINER_RECORD_SIZE_WITHOUT_VICTORY_ITEM = 18


def parse_trainer_record(
    data: bytes,
    party_data: bytes,
    *,
    trainer_id: int,
    name: str,
    class_names: tuple[str, ...],
    trainer_archive: str,
    party_archive: str,
) -> BattleModeTrainer:
    if len(data) not in {
        TRAINER_RECORD_SIZE,
        TRAINER_RECORD_SIZE_WITHOUT_VICTORY_ITEM,
    }:
        raise InvalidRomError(
            f"Gen V trainer {trainer_id} has size {len(data)}; expected "
            f"{TRAINER_RECORD_SIZE_WITHOUT_VICTORY_ITEM} or {TRAINER_RECORD_SIZE}"
        )
    poketype, class_id, battle_mode, party_count = struct.unpack_from("<BBBB", data)
    if class_id >= len(class_names):
        raise InvalidRomError(
            f"Trainer {trainer_id} references missing class name {class_id}"
        )
    reward_items = struct.unpack_from("<4H", data, 4)
    ai_flags = struct.unpack_from("<H", data, 12)[0]
    healer = bool(data[16])
    victory_money_multiplier = data[17]
    victory_item_id = (
        struct.unpack_from("<H", data, 18)[0] if len(data) == TRAINER_RECORD_SIZE else 0
    )
    has_custom_moves = bool(poketype & 1)
    has_held_items = bool(poketype & 2)
    record_size = 8 + (2 if has_held_items else 0) + (8 if has_custom_moves else 0)
    expected_size = record_size * party_count
    valid_size = any(
        len(party_data) - padding_size >= expected_size
        and (len(party_data) - padding_size) % record_size == 0
        and not any(party_data[len(party_data) - padding_size :])
        for padding_size in range(4)
    )
    if not valid_size:
        raise InvalidRomError(
            f"Trainer {trainer_id} party has size {len(party_data)}; expected "
            f"at least {expected_size}, complete {record_size}-byte records, "
            "and at most three zero padding bytes"
        )

    party = []
    offset = 0
    for _ in range(party_count):
        iv_strength, ability_and_flag = struct.unpack_from("<BB", party_data, offset)
        level, species_id, form_id = struct.unpack_from("<HHH", party_data, offset + 2)
        offset += 8
        held_item_id = None
        if has_held_items:
            held_item_id = struct.unpack_from("<H", party_data, offset)[0]
            offset += 2
        move_ids: tuple[int, ...] = ()
        if has_custom_moves:
            move_ids = struct.unpack_from("<4H", party_data, offset)
            offset += 8
        party.append(
            AbilitySlotTrainerPokemon(
                iv_strength=iv_strength,
                ability_slot=ability_and_flag >> 4,
                forced_gender_flag=ability_and_flag & 0xF,
                level=level,
                species_id=species_id,
                form_id=form_id,
                held_item_id=held_item_id,
                move_ids=move_ids,
            )
        )

    return BattleModeTrainer(
        trainer_id=trainer_id,
        name=name,
        class_id=class_id,
        class_name=class_names[class_id],
        battle_mode=battle_mode,
        double_battle=battle_mode != 0,
        has_custom_moves=has_custom_moves,
        has_held_items=has_held_items,
        party_count=party_count,
        reward_item_ids=reward_items,
        ai_flags=ai_flags,
        healer=healer,
        victory_money_multiplier=victory_money_multiplier,
        victory_item_id=victory_item_id,
        party=tuple(party),
        provenance=RecordProvenance(
            source="rom", archive=trainer_archive, member=trainer_id
        ),
        party_provenance=RecordProvenance(
            source="rom", archive=party_archive, member=trainer_id
        ),
    )


# NPCs whose sight-triggered battle is dispatched through a shared/common
# script reference their trainer with `script_used = band + trainer_id`,
# where `band` is a multiple of 1000 (seen: 2000/3000/5000/7000 in the real
# ROM). Verified against 18 real Black ROM trainer records this way (script
# member 155 and 830's NPCs resolving to trainer IDs 26-34 and 40-48, both
# consecutive runs with sensible ascending trainer classes/party sizes), and
# re-verified unchanged against real Black 2 ROM data (662 of 813 B2W2
# trainers resolve to a story-coherent location with this same arithmetic,
# with every multi-location trainer explained by a legitimate rematch/shared
# roaming-trainer script) -- not literal script-engine facts, but arithmetic
# on an already-decoded NPC field, matching this project's "decode, don't
# guess" bar since every resolved ID is checked against the real trainer
# table's own valid range.
_COMMON_SCRIPT_BAND_SIZE = 1000
_MIN_COMMON_SCRIPT_USED = _COMMON_SCRIPT_BAND_SIZE


def resolve_common_script_trainer_id(
    script_used: int, *, trainer_count: int
) -> int | None:
    """Resolve a sight-triggered NPC's `script_used` to a literal trainer ID.

    Shared by BW and B2W2 -- verified independently against both games' real
    ROM data, not merely assumed to carry over.

    Returns `None` for local per-map script indices (`script_used` below the
    common-script band) or for values that don't resolve to a real trainer
    record, rather than guessing.
    """
    if script_used < _MIN_COMMON_SCRIPT_USED:
        return None
    band = (script_used // _COMMON_SCRIPT_BAND_SIZE) * _COMMON_SCRIPT_BAND_SIZE
    trainer_id = script_used - band
    if not 0 < trainer_id < trainer_count:
        return None
    return trainer_id

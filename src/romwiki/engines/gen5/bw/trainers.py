from __future__ import annotations

import struct

from romwiki.schema import (
    AbilitySlotTrainerPokemon,
    BattleModeTrainer,
    RecordProvenance,
)
from romwiki.util.errors import InvalidRomError

TRAINER_RECORD_SIZE = 20


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
    if len(data) != TRAINER_RECORD_SIZE:
        raise InvalidRomError(
            f"Gen V trainer {trainer_id} has size {len(data)}; expected "
            f"{TRAINER_RECORD_SIZE}"
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
    victory_item_id = struct.unpack_from("<H", data, 18)[0]
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
        difficulty, ability_and_flag = struct.unpack_from("<BB", party_data, offset)
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
                difficulty=difficulty,
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

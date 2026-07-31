from __future__ import annotations

import struct

from romwiki.schema import ClassGenderTrainer, RecordProvenance, TrainerPokemon
from romwiki.util.errors import InvalidRomError

TRAINER_RECORD_SIZE = 20


def parse_trainer_class_genders(data: bytes, *, count: int) -> tuple[str, ...]:
    if len(data) != count:
        raise InvalidRomError(
            f"Gen IV trainer class gender table has size {len(data)}; expected {count}"
        )
    if invalid := sorted(set(data) - {0, 1, 2}):
        raise InvalidRomError(
            f"Gen IV trainer class gender table contains unknown values: {invalid}"
        )
    # The engine treats only 1 as female; 0 and the mixed/double class value 2
    # both take the male PID path.
    return tuple("female" if value == 1 else "male" for value in data)


def parse_trainer_class_prize_multipliers(
    data: bytes, *, count: int
) -> tuple[int, ...]:
    if len(data) != count:
        raise InvalidRomError(
            "Gen IV trainer class prize multiplier table has size "
            f"{len(data)}; expected {count}"
        )
    return tuple(data)


def parse_trainer_record(
    data: bytes,
    party_data: bytes,
    *,
    trainer_id: int,
    name: str,
    class_names: tuple[str, ...],
    class_genders: tuple[str, ...],
    class_prize_multipliers: tuple[int, ...],
    trainer_archive: str,
    party_archive: str,
) -> ClassGenderTrainer:
    if len(data) != TRAINER_RECORD_SIZE:
        raise InvalidRomError(
            f"Gen IV trainer {trainer_id} has size {len(data)}; expected 20"
        )
    flags, class_id, unknown_byte, party_count = struct.unpack_from("<BBBB", data)
    if class_id >= len(class_names):
        raise InvalidRomError(
            f"Trainer {trainer_id} references missing class name {class_id}"
        )
    if class_id >= len(class_genders):
        raise InvalidRomError(
            f"Trainer {trainer_id} references missing class gender {class_id}"
        )
    if class_id >= len(class_prize_multipliers):
        raise InvalidRomError(
            f"Trainer {trainer_id} references missing class prize multiplier "
            f"{class_id}"
        )
    reward_items = struct.unpack_from("<4H", data, 4)
    ai_flags, battle_type = struct.unpack_from("<II", data, 12)
    has_custom_moves = bool(flags & 1)
    has_held_items = bool(flags & 2)
    record_size = 8 + (2 if has_held_items else 0) + (8 if has_custom_moves else 0)
    expected_size = record_size * party_count
    if len(party_data) < expected_size:
        raise InvalidRomError(
            f"Trainer {trainer_id} party is truncated: {len(party_data)} bytes; "
            f"expected at least {expected_size}"
        )

    party = []
    offset = 0
    for _ in range(party_count):
        difficulty, gender_ability, level, species_form = struct.unpack_from(
            "<BBHH", party_data, offset
        )
        offset += 6
        held_item_id = None
        if has_held_items:
            held_item_id = struct.unpack_from("<H", party_data, offset)[0]
            offset += 2
        move_ids: tuple[int, ...] = ()
        if has_custom_moves:
            moves = struct.unpack_from("<4H", party_data, offset)
            move_ids = tuple(0 if move == 0xFFFF else move for move in moves)
            offset += 8
        ball_seal = struct.unpack_from("<H", party_data, offset)[0]
        offset += 2
        party.append(
            TrainerPokemon(
                difficulty=difficulty,
                gender_ability=gender_ability,
                level=level,
                species_id=species_form & 0x3FF,
                form_id=species_form >> 10,
                held_item_id=held_item_id,
                move_ids=move_ids,
                ball_seal=ball_seal,
            )
        )

    return ClassGenderTrainer(
        trainer_id=trainer_id,
        name=name,
        class_id=class_id,
        class_name=class_names[class_id],
        class_gender=class_genders[class_id],
        victory_money_multiplier=class_prize_multipliers[class_id],
        has_custom_moves=has_custom_moves,
        has_held_items=has_held_items,
        unknown_byte=unknown_byte,
        party_count=party_count,
        reward_item_ids=reward_items,
        ai_flags=ai_flags,
        battle_type=battle_type,
        double_battle=battle_type == 2,
        party=tuple(party),
        trailing_party_data=party_data[offset:],
        provenance=RecordProvenance(
            source="rom", archive=trainer_archive, member=trainer_id
        ),
        party_provenance=RecordProvenance(
            source="rom", archive=party_archive, member=trainer_id
        ),
    )

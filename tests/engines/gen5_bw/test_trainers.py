from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen5_bw.trainers import parse_trainer_record
from romwiki.util.errors import InvalidRomError

_CLASS_NAMES = ("Youngster", "Lass", "Leader")


def _trainer_header(
    *,
    poketype: int,
    class_id: int,
    battle_mode: int,
    party_count: int,
    battle_items: tuple[int, int, int, int] = (0, 0, 0, 0),
    ai_flags: int = 0,
    healer: int = 0,
    victory_money: int = 0,
    victory_item: int = 0,
) -> bytes:
    return struct.pack(
        "<BBBB4HH2xBBH",
        poketype,
        class_id,
        battle_mode,
        party_count,
        *battle_items,
        ai_flags,
        healer,
        victory_money,
        victory_item,
    )


class Gen5TrainerTests(unittest.TestCase):
    def test_decodes_a_simple_single_pokemon_party(self) -> None:
        # Real Black ROM trainer 2 (Lass Jimmy): a level 7 Purrloin, no
        # held item, no custom moves.
        data = _trainer_header(
            poketype=0, class_id=1, battle_mode=0, party_count=1
        )
        party_data = struct.pack("<BBHHH", 0, 0, 7, 509, 0)

        trainer = parse_trainer_record(
            data,
            party_data,
            trainer_id=2,
            name="Jimmy",
            class_names=_CLASS_NAMES,
            trainer_archive="trainers.narc",
            party_archive="parties.narc",
        )

        self.assertEqual(trainer.class_name, "Lass")
        self.assertFalse(trainer.double_battle)
        self.assertEqual(len(trainer.party), 1)
        self.assertEqual(trainer.party[0].species_id, 509)
        self.assertEqual(trainer.party[0].level, 7)
        self.assertIsNone(trainer.party[0].held_item_id)
        self.assertEqual(trainer.party[0].move_ids, ())

    def test_decodes_held_items_and_custom_moves(self) -> None:
        data = _trainer_header(
            poketype=3, class_id=2, battle_mode=3, party_count=1
        )
        party_data = struct.pack(
            "<BBHHHH4H", 0, 0, 75, 510, 0, 0, 391, 400, 176, 202
        )

        trainer = parse_trainer_record(
            data,
            party_data,
            trainer_id=542,
            name="Cheren",
            class_names=_CLASS_NAMES,
            trainer_archive="trainers.narc",
            party_archive="parties.narc",
        )

        self.assertTrue(trainer.has_held_items)
        self.assertTrue(trainer.has_custom_moves)
        self.assertEqual(trainer.battle_mode, 3)
        self.assertTrue(trainer.double_battle)
        member = trainer.party[0]
        self.assertEqual(member.held_item_id, 0)
        self.assertEqual(member.move_ids, (391, 400, 176, 202))

    def test_decodes_ability_slot_and_forced_gender(self) -> None:
        # Real Black ROM trainer 23 (Gym Leader Burgh): a forced-male and a
        # forced-female Emolga.
        data = _trainer_header(poketype=0, class_id=2, battle_mode=0, party_count=1)
        ability_and_flag = (0 << 4) | 1
        party_data = struct.pack("<BBHHH", 0, ability_and_flag, 25, 587, 0)

        trainer = parse_trainer_record(
            data,
            party_data,
            trainer_id=23,
            name="Burgh",
            class_names=_CLASS_NAMES,
            trainer_archive="trainers.narc",
            party_archive="parties.narc",
        )
        self.assertEqual(trainer.party[0].forced_gender_flag, 1)
        self.assertEqual(trainer.party[0].ability_slot, 0)

    def test_rejects_wrong_header_size(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_trainer_record(
                b"short",
                b"",
                trainer_id=1,
                name="x",
                class_names=_CLASS_NAMES,
                trainer_archive="trainers.narc",
                party_archive="parties.narc",
            )

    def test_rejects_mismatched_party_size(self) -> None:
        data = _trainer_header(poketype=0, class_id=0, battle_mode=0, party_count=2)
        with self.assertRaises(InvalidRomError):
            parse_trainer_record(
                data,
                struct.pack("<BBHHH", 0, 0, 5, 1, 0),
                trainer_id=1,
                name="x",
                class_names=_CLASS_NAMES,
                trainer_archive="trainers.narc",
                party_archive="parties.narc",
            )

    def test_rejects_unknown_class_id(self) -> None:
        data = _trainer_header(
            poketype=0, class_id=len(_CLASS_NAMES), battle_mode=0, party_count=0
        )
        with self.assertRaises(InvalidRomError):
            parse_trainer_record(
                data,
                b"",
                trainer_id=1,
                name="x",
                class_names=_CLASS_NAMES,
                trainer_archive="trainers.narc",
                party_archive="parties.narc",
            )


if __name__ == "__main__":
    unittest.main()

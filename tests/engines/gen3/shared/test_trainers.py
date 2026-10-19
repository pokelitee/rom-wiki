from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen3.shared.trainers import (
    parse_trainer_money_table,
    parse_trainer_record,
    party_record_size,
)
from romwiki.util.errors import InvalidRomError


def _header(
    *,
    party_flags: int,
    class_id: int = 0x54,
    name: bytes = bytes((0xBC, 0xCC, 0xC9, 0xBD, 0xC5, 0xFF)),  # "BROCK"
    reward_items: tuple[int, int, int, int] = (0, 0, 0, 0),
    double_battle: bool = False,
    ai_flags: int = 7,
    party_size: int = 2,
    party_pointer: int = 0x0823C610,
) -> bytes:
    data = bytearray(0x28)
    data[0] = party_flags
    data[1] = class_id
    data[4 : 4 + len(name)] = name
    struct.pack_into("<4H", data, 0x10, *reward_items)
    data[0x18] = 1 if double_battle else 0
    struct.pack_into("<I", data, 0x1C, ai_flags)
    data[0x20] = party_size
    struct.pack_into("<I", data, 0x24, party_pointer)
    return bytes(data)


def _party_member(
    *, iv: int, level: int, species: int, held_item: int, moves: tuple[int, ...] = ()
) -> bytes:
    data = bytearray(8 + (8 if moves else 0))
    struct.pack_into("<HHHH", data, 0, iv, level, species, held_item)
    if moves:
        struct.pack_into("<4H", data, 8, *moves)
    return bytes(data)


class Gen3TrainerDataTests(unittest.TestCase):
    def test_decodes_a_custom_moves_only_party(self) -> None:
        header = _header(party_flags=1, party_size=2)
        party = _party_member(
            iv=0, level=12, species=74, held_item=0, moves=(33, 111, 0, 0)
        ) + _party_member(iv=0, level=14, species=95, held_item=0, moves=(33, 20, 0, 0))

        record = parse_trainer_record(
            header, party, trainer_id=414, archive_path="offset:0x0"
        )

        self.assertEqual(record.trainer_id, 414)
        self.assertEqual(record.name, "Brock")
        self.assertEqual(record.class_id, 0x54)
        self.assertFalse(record.double_battle)
        self.assertEqual(record.battle_mode, 0)
        self.assertTrue(record.has_custom_moves)
        self.assertFalse(record.has_held_items)
        self.assertEqual(record.party_count, 2)
        self.assertEqual(len(record.party), 2)
        geodude, onix = record.party
        self.assertEqual(geodude.species_id, 74)
        self.assertEqual(geodude.level, 12)
        self.assertIsNone(geodude.held_item_id)
        self.assertEqual(geodude.move_ids, (33, 111, 0, 0))
        self.assertEqual(onix.species_id, 95)
        self.assertEqual(onix.level, 14)
        # Ability/gender/form aren't stored per party slot in Generation III.
        self.assertEqual(geodude.ability_slot, 0)
        self.assertEqual(geodude.forced_gender_flag, 0)
        self.assertEqual(geodude.form_id, 0)
        self.assertEqual(record.provenance.member, 414)
        self.assertEqual(record.provenance.source, "rom")

    def test_decodes_a_held_item_only_party_with_no_moves(self) -> None:
        header = _header(party_flags=2, party_size=2)
        party = _party_member(iv=100, level=37, species=106, held_item=207) + (
            _party_member(iv=100, level=37, species=107, held_item=207)
        )

        record = parse_trainer_record(
            header, party, trainer_id=317, archive_path="offset:0x0"
        )

        self.assertTrue(record.has_held_items)
        self.assertFalse(record.has_custom_moves)
        hitmonlee, hitmonchan = record.party
        self.assertEqual(hitmonlee.held_item_id, 207)
        self.assertEqual(hitmonlee.move_ids, ())
        self.assertEqual(hitmonchan.held_item_id, 207)

    def test_decodes_a_no_flags_party(self) -> None:
        header = _header(party_flags=0, party_size=1)
        party = _party_member(iv=0, level=5, species=23, held_item=0)

        record = parse_trainer_record(
            header, party, trainer_id=1, archive_path="offset:0x0"
        )

        self.assertFalse(record.has_custom_moves)
        self.assertFalse(record.has_held_items)
        self.assertIsNone(record.party[0].held_item_id)

    def test_reports_undecoded_fields_as_none_rather_than_zero(self) -> None:
        header = _header(party_flags=0, party_size=1)
        party = _party_member(iv=0, level=5, species=23, held_item=0)

        record = parse_trainer_record(
            header, party, trainer_id=1, archive_path="offset:0x0"
        )

        self.assertIsNone(record.class_name)
        self.assertIsNone(record.healer)
        self.assertIsNone(record.victory_money_multiplier)
        self.assertIsNone(record.victory_item_id)

    def test_rejects_an_unexpected_header_size(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_trainer_record(b"short", b"", trainer_id=1, archive_path="offset:0x0")

    def test_rejects_a_mismatched_party_size(self) -> None:
        header = _header(party_flags=1, party_size=2)
        with self.assertRaises(InvalidRomError):
            parse_trainer_record(
                header, b"\x00" * 10, trainer_id=1, archive_path="offset:0x0"
            )


class PartyRecordSizeTests(unittest.TestCase):
    def test_base_record_is_eight_bytes(self) -> None:
        self.assertEqual(party_record_size(has_custom_moves=False), 8)

    def test_custom_moves_adds_eight_bytes(self) -> None:
        self.assertEqual(party_record_size(has_custom_moves=True), 16)


class ParseTrainerMoneyTableTests(unittest.TestCase):
    def test_reads_classes_until_the_terminator_and_its_default(self) -> None:
        data = bytes(
            [0x54, 25, 0, 0, 0x51, 4, 0, 0, 0x54, 9, 0, 0, 0xFF, 5, 0, 0, 1, 2]
        )

        values, default = parse_trainer_money_table(data)

        # The game stops at a class's first entry.
        self.assertEqual(values, {0x54: (25, 0), 0x51: (4, 1)})
        self.assertEqual(default, (5, 3))

    def test_rejects_a_table_without_a_terminator(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_trainer_money_table(bytes([1, 2, 0, 0]))


if __name__ == "__main__":
    unittest.main()

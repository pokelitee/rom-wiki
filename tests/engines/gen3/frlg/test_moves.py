from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen3.frlg.moves import parse_move_record
from romwiki.util.errors import InvalidRomError


class Gen3MoveDataTests(unittest.TestCase):
    def _record(
        self,
        *,
        effect: int = 0,
        power: int = 40,
        type_id: int = 0,
        accuracy: int = 100,
        pp: int = 35,
        chance: int = 0,
        target: int = 0,
        priority: int = 0,
        flags: int = 0x33,
    ) -> bytes:
        data = bytearray(12)
        data[0] = effect
        data[1] = power
        data[2] = type_id
        data[3] = accuracy
        data[4] = pp
        data[5] = chance
        data[6] = target
        struct.pack_into("<b", data, 7, priority)
        struct.pack_into("<I", data, 8, flags)
        return bytes(data)

    def test_decodes_pound_stats_and_provenance(self) -> None:
        record = parse_move_record(self._record(), move_id=1, archive_path="offset:0x0")

        self.assertEqual(record.effect_id, 0)
        self.assertEqual(record.power, 40)
        self.assertEqual(record.type_id, 0)
        self.assertEqual(record.accuracy, 100)
        self.assertEqual(record.pp, 35)
        self.assertEqual(record.effect_chance, 0)
        self.assertEqual(record.target_id, 0)
        self.assertEqual(record.priority, 0)
        self.assertEqual(record.flags, 0x33)
        self.assertEqual(record.damage_class_id, 1)
        self.assertIsNone(record.contest_effect_id)
        self.assertIsNone(record.contest_type_id)
        self.assertEqual(record.provenance.member, 1)
        self.assertEqual(record.provenance.archive, "offset:0x0")
        self.assertEqual(record.provenance.source, "rom")

    def test_classifies_tackle_as_physical(self) -> None:
        record = parse_move_record(
            self._record(power=35, type_id=0, accuracy=95, pp=35),
            move_id=33,
            archive_path="offset:0x0",
        )

        self.assertEqual(record.damage_class_id, 1)

    def test_classifies_a_status_move_as_status_regardless_of_type(self) -> None:
        record = parse_move_record(
            self._record(power=0, type_id=0, accuracy=100, pp=40),
            move_id=45,
            archive_path="offset:0x0",
        )

        self.assertEqual(record.damage_class_id, 0)

    def test_classifies_a_special_type_move_as_special(self) -> None:
        record = parse_move_record(
            self._record(power=40, type_id=10, accuracy=100, pp=25),
            move_id=52,
            archive_path="offset:0x0",
        )

        self.assertEqual(record.damage_class_id, 2)

    def test_reads_negative_priority(self) -> None:
        record = parse_move_record(
            self._record(priority=-6), move_id=1, archive_path="offset:0x0"
        )

        self.assertEqual(record.priority, -6)

    def test_rejects_an_unexpected_record_size(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_move_record(b"short", move_id=1, archive_path="offset:0x0")


if __name__ == "__main__":
    unittest.main()

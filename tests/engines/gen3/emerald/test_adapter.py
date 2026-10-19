from __future__ import annotations

import struct
import unittest

import romwiki.engines.gen3.emerald as emerald
import romwiki.engines.gen3.frlg as frlg
from romwiki.engines.gen3.shared.encounters import parse_encounter_record
from romwiki.engines.gen3.shared.trainers import parse_trainer_record
from romwiki.engines.registry import GEN3_EMERALD_ENGINE, get_engine
from romwiki.util.errors import InvalidRomError


def _trainer_header(*, party_size: int) -> bytes:
    data = bytearray(0x28)
    data[1] = 0x0D  # trainer class
    data[4:9] = bytes((0xC1, 0xCC, 0xDF, 0xC8, 0xFF))  # "GRUNT"-style name bytes
    data[0x20] = party_size
    struct.pack_into("<I", data, 0x24, 0x08310000)
    return bytes(data)


def _party_member(*, level: int, species: int) -> bytes:
    return struct.pack("<HHHH", 0, level, species, 0)


class Gen3EmeraldAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = get_engine(GEN3_EMERALD_ENGINE)

    def test_exposes_emerald_record_counts_rather_than_fire_red_counts(self) -> None:
        self.assertEqual(self.engine.items.ITEM_RECORD_COUNT, 377)
        self.assertEqual(self.engine.trainers.TRAINER_RECORD_COUNT, 855)
        self.assertEqual(emerald.ENCOUNTER_HEADER_COUNT, 124)
        self.assertNotEqual(emerald.ITEM_RECORD_COUNT, frlg.ITEM_RECORD_COUNT)
        self.assertNotEqual(emerald.TRAINER_RECORD_COUNT, frlg.TRAINER_RECORD_COUNT)
        self.assertNotEqual(emerald.ENCOUNTER_HEADER_COUNT, frlg.ENCOUNTER_HEADER_COUNT)

    def test_reuses_the_shared_generation_iii_record_parsers(self) -> None:
        self.assertIs(self.engine.trainers.parse_trainer_record, parse_trainer_record)
        self.assertIs(
            self.engine.encounters.parse_encounter_record, parse_encounter_record
        )
        self.assertIs(
            self.engine.trainers.parse_trainer_record, frlg.parse_trainer_record
        )

    def test_declares_flat_tutors_but_no_pickup_data(self) -> None:
        self.assertEqual(self.engine.formats.tutors, "flat-offset-table")
        self.assertEqual(self.engine.tutors.TUTOR_MOVE_COUNT, 30)
        self.assertEqual(len(self.engine.tutors.TUTOR_LOCATIONS), 30)
        self.assertEqual(self.engine.formats.pickup, "none")
        self.assertEqual(self.engine.formats.static_encounters, "none")

    def test_decodes_a_trainer_through_the_adapter(self) -> None:
        party = _party_member(level=5, species=261) + _party_member(
            level=7, species=263
        )

        record = self.engine.trainers.parse_trainer_record(
            _trainer_header(party_size=2),
            party,
            trainer_id=1,
            archive_path="offset:0x310030",
        )

        self.assertEqual(record.class_id, 0x0D)
        self.assertEqual(record.party_count, 2)
        self.assertEqual(
            [(member.level, member.species_id) for member in record.party],
            [(5, 261), (7, 263)],
        )
        self.assertIsNone(record.class_name)

    def test_rejects_a_party_that_does_not_match_the_declared_size(self) -> None:
        with self.assertRaises(InvalidRomError):
            self.engine.trainers.parse_trainer_record(
                _trainer_header(party_size=2),
                _party_member(level=5, species=261),
                trainer_id=1,
                archive_path="offset:0x310030",
            )


class Gen3EmeraldTutorTests(unittest.TestCase):
    def test_reads_four_byte_masks_covering_all_thirty_tutors(self) -> None:
        bits = (1 << 0) | (1 << 15) | (1 << 29)

        record = emerald.parse_tutor_compatibility(
            struct.pack("<I", bits), species_id=1, table_index=0
        )

        assert record is not None
        self.assertEqual(record.tutor_ids, (1, 16, 30))

    def test_rejects_a_two_byte_mask(self) -> None:
        with self.assertRaises(InvalidRomError):
            emerald.parse_tutor_compatibility(
                struct.pack("<H", 1), species_id=1, table_index=0
            )


if __name__ == "__main__":
    unittest.main()

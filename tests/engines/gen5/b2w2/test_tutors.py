from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen5.b2w2.tutors import (
    TUTOR_COMPATIBILITY_OFFSET,
    TUTOR_COUNT,
    parse_tutor_compatibility_record,
    parse_tutor_move_table,
)


class B2W2TutorTests(unittest.TestCase):
    def test_decodes_move_groups_and_shard_costs(self) -> None:
        data = b"".join(
            struct.pack("<III", index + 1, 2, 0) for index in range(TUTOR_COUNT)
        )

        records = parse_tutor_move_table(data)

        self.assertEqual(records[0].shard_costs.yellow, 2)
        self.assertEqual(records[13].shard_costs.red, 2)
        self.assertEqual(records[28].shard_costs.blue, 2)
        self.assertEqual(records[43].shard_costs.green, 2)

    def test_unscrambles_personal_compatibility_groups(self) -> None:
        data = bytearray(TUTOR_COMPATIBILITY_OFFSET + 16)
        data[TUTOR_COMPATIBILITY_OFFSET] = 1
        data[TUTOR_COMPATIBILITY_OFFSET + 8] = 1

        record = parse_tutor_compatibility_record(bytes(data), personal_member=1)

        self.assertEqual(record.tutor_ids, (1, 14))


if __name__ == "__main__":
    unittest.main()

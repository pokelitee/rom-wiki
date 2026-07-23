from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen4_dppt import Gen4BerryData, parse_berry_record
from romwiki.util.errors import InvalidRomError


class Gen4BerryTests(unittest.TestCase):
    def test_parses_cheri_berry_record(self) -> None:
        data = struct.pack("<HBBBBBBBBBB", 20, 2, 1, 3, 15, 10, 0, 0, 0, 0, 25)

        berry = parse_berry_record(data)

        self.assertEqual(
            berry,
            Gen4BerryData(
                size=20,
                firmness=2,
                base_yield=1,
                stage_duration=3,
                moisture_drain_rate=15,
                spiciness=10,
                dryness=0,
                sweetness=0,
                bitterness=0,
                sourness=0,
                smoothness=25,
            ),
        )

    def test_rejects_truncated_record(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_berry_record(b"\x00" * 5)


if __name__ == "__main__":
    unittest.main()

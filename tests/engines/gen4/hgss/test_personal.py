from __future__ import annotations

import unittest

from romwiki.engines.gen4.hgss import parse_personal_record
from romwiki.util.errors import InvalidRomError


class HgssPersonalDataTests(unittest.TestCase):
    def test_decodes_a_real_retail_bulbasaur_record(self) -> None:
        data = bytes.fromhex(
            "2d31312d41410c032d400001000000001f144603010741000003000020073584"
            "081e10022024669202000000"
        )

        record = parse_personal_record(
            data, species_id=1, archive_path="a/0/0/2"
        )

        self.assertEqual(
            (
                record.base_stats.hp,
                record.base_stats.attack,
                record.base_stats.defense,
                record.base_stats.speed,
                record.base_stats.special_attack,
                record.base_stats.special_defense,
            ),
            (45, 49, 49, 45, 65, 65),
        )
        self.assertEqual(record.type_ids, (12, 3))
        self.assertEqual(record.ability_ids, (65, 0))
        self.assertEqual(record.machine_ids[-3:], (93, 96, 98))
        self.assertEqual(record.provenance.archive, "a/0/0/2")

    def test_rejects_an_unexpected_record_size(self) -> None:
        with self.assertRaisesRegex(InvalidRomError, "expected 44"):
            parse_personal_record(
                b"short", species_id=1, archive_path="a/0/0/2"
            )


if __name__ == "__main__":
    unittest.main()

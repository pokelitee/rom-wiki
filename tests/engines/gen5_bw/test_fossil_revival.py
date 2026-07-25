from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen5_bw.scripts import parse_fossil_revival_table


def _fossil_check(*, item_id: int, species_id: int) -> bytes:
    return (
        struct.pack("<HH", 0x9, 32802)
        + struct.pack("<HH", 0x8, item_id)
        + struct.pack("<HH", 0x11, 1)
        + struct.pack("<H", 0x1F)
        + bytes((255,))
        + struct.pack("<i", 12)
        + struct.pack("<HHH", 0x28, 32803, species_id)
    )


class Gen5FossilRevivalTests(unittest.TestCase):
    def test_extracts_real_fossil_item_to_species_pairs(self) -> None:
        # Real Black/White ROM facts (script file 877, byte-identical between
        # versions): Skull->Cranidos, Armor->Shieldon, Helix->Omanyte,
        # Dome->Kabuto, Old Amber->Aerodactyl, Claw->Anorith, Root->Lileep,
        # Cover->Tirtouga, Plume->Archen -- decoded from the script's own
        # bytecode via the same opcode table §4's trainer-battle work
        # verified, not adopted from external game knowledge.
        pairs = [
            (105, 408),
            (104, 410),
            (101, 138),
            (102, 140),
            (103, 142),
            (100, 347),
            (99, 345),
            (572, 564),
            (573, 566),
        ]
        data = b"".join(
            _fossil_check(item_id=item_id, species_id=species_id)
            for item_id, species_id in pairs
        )

        revivals = parse_fossil_revival_table(data)

        self.assertEqual(
            [(r.item_id, r.species_id) for r in revivals], pairs
        )

    def test_ignores_unrelated_variables(self) -> None:
        body = (
            struct.pack("<HH", 0x9, 12345)
            + struct.pack("<HH", 0x8, 105)
            + struct.pack("<HH", 0x11, 1)
            + struct.pack("<H", 0x1F)
            + bytes((255,))
            + struct.pack("<i", 12)
            + struct.pack("<HHH", 0x28, 32803, 408)
        )

        self.assertEqual(parse_fossil_revival_table(body), ())

    def test_ignores_wrong_comparison_operator(self) -> None:
        body = (
            struct.pack("<HH", 0x9, 32802)
            + struct.pack("<HH", 0x8, 105)
            + struct.pack("<HH", 0x11, 2)
            + struct.pack("<H", 0x1F)
            + bytes((255,))
            + struct.pack("<i", 12)
            + struct.pack("<HHH", 0x28, 32803, 408)
        )

        self.assertEqual(parse_fossil_revival_table(body), ())

    def test_empty_data_has_no_revivals(self) -> None:
        self.assertEqual(parse_fossil_revival_table(b""), ())


if __name__ == "__main__":
    unittest.main()

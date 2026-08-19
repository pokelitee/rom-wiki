from __future__ import annotations

import unittest

from romwiki.engines.gen5.script_disassembler import Gen5Instruction
from romwiki.engines.gen5.static_encounter_dedup import (
    deduplicate_exact_paths,
    deduplicate_wild_paths,
)


def _instruction(offset: int, name: str = "CallWildBattle") -> Gen5Instruction:
    return Gen5Instruction(offset, 0x178, name, (), offset + 8)


class StaticEncounterDedupTests(unittest.TestCase):
    def test_keeps_the_same_fact_at_two_different_members(self) -> None:
        # Real, verified BW1 shape: N's Castle and Dragonspiral Tower both
        # call `CallWildBattle` for the same species at the same level, at
        # two different script members. A fact-only dedup (BW1's own bug,
        # fixed by this module) silently drops the second one; the real
        # member-aware dedup must keep both.
        castle = ((643, 50, False), 556, _instruction(3322))
        tower = ((643, 50, False), 426, _instruction(345))

        kept = deduplicate_exact_paths([tower, castle])

        self.assertEqual(sorted(member for _, member, _ in kept), [426, 556])

    def test_collapses_repeated_identical_fact_within_one_member(self) -> None:
        # Real, verified shape: Desert Resort calls the same species+level
        # `CallWildBattle` at several different offsets within one member --
        # a single conceptual encounter opportunity, correctly collapsed to
        # one record.
        candidates = [
            ((555, 35, False), 316, _instruction(871)),
            ((555, 35, False), 316, _instruction(1077)),
            ((555, 35, False), 316, _instruction(1283)),
        ]

        kept = deduplicate_exact_paths(candidates)

        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0][1], 316)

    def test_wild_paths_keep_the_lowest_level_lifecycle_alternative(self) -> None:
        initial = ((637, 45, False), 1, _instruction(10))
        rematch = ((637, 65, False), 1, _instruction(30))

        kept = deduplicate_wild_paths([rematch, initial])

        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0][0], (637, 45, False))

    def test_wild_paths_still_keep_the_same_species_at_a_different_member(self) -> None:
        here = ((637, 45, False), 1, _instruction(10))
        elsewhere = ((637, 45, False), 2, _instruction(50))

        kept = deduplicate_wild_paths([here, elsewhere])

        self.assertEqual(sorted(member for _, member, _ in kept), [1, 2])


if __name__ == "__main__":
    unittest.main()

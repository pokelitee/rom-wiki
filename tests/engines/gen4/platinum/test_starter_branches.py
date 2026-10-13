from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen4.platinum import (
    parse_starter_branch_families,
    parse_starter_species,
)
from romwiki.util.errors import InvalidRomError
from tests.conftest import make_script

_STARTER_VAR = 0x800C
_HEADER = 6  # make_script's table: relative offset (4) + terminator (2)


def _get_starter() -> bytes:
    return struct.pack("<HH", 0x00DE, _STARTER_VAR)


def _battle(trainer_id: int) -> bytes:
    # Battle command plus the following real command that validates it.
    return struct.pack("<HHHH", 0x00E5, trainer_id, 0, 0x0016)


def _branch_to(species: int, target: int, *, from_offset: int) -> bytes:
    """CompareVarToValue + GotoIf whose relative offset resolves to `target`."""
    relative_field = from_offset + 6 + 3
    relative = target - (relative_field + 4)
    return (
        struct.pack("<HHH", 0x0011, _STARTER_VAR, species)
        + struct.pack("<HB", 0x001C, 0)
        + struct.pack("<i", relative)
    )


_BRANCH_SIZE = 13


def _script(*, species_targets, battles, include_starter_read=True):
    """Build a script whose branches jump onto the requested battles.

    Layout: [starter read] [branch...] [battle...] so battle offsets are known
    before the branches are encoded.
    """
    read = _get_starter() if include_starter_read else b""
    branch_area = _BRANCH_SIZE * len(species_targets)
    battles_at = _HEADER + len(read) + branch_area

    offsets = {}
    cursor = battles_at
    for trainer_id in battles:
        offsets[trainer_id] = cursor
        cursor += len(_battle(trainer_id))

    body = read
    from_offset = _HEADER + len(read)
    for species, trainer_id in species_targets:
        body += _branch_to(species, offsets[trainer_id], from_offset=from_offset)
        from_offset += _BRANCH_SIZE
    for trainer_id in battles:
        body += _battle(trainer_id)
    return make_script(body)


class Gen4StarterBranchTests(unittest.TestCase):
    def test_decodes_species_to_record_and_the_fallthrough(self) -> None:
        data = _script(
            species_targets=((387, 248), (390, 249)),
            battles=(247, 248, 249),
        )

        families = parse_starter_branch_families(
            data, script_file_id=429, trainer_count=928
        )

        self.assertEqual(len(families), 1)
        family = families[0]
        self.assertEqual(family.script_file_id, 429)
        self.assertEqual(family.selected, ((387, 248), (390, 249)))
        self.assertEqual(family.fallthrough_trainer_id, 247)
        self.assertEqual(family.trainer_ids, (248, 249, 247))

    def test_decodes_the_fallthrough_when_it_is_laid_out_after_the_branches(
        self,
    ) -> None:
        # Retail Platinum emits the fall-through battle's bytes before the
        # branched battles; Renegade Platinum emits it after them instead
        # (see `_fallthrough_staged`'s own docstring). Only `battles`' order
        # changes here -- the branch targets (248, 249) are laid out first
        # in the byte stream and the fall-through (247) last, the opposite
        # of `test_decodes_species_to_record_and_the_fallthrough` above --
        # to lock in that this is resolved by scanning either side of the
        # branched region rather than assuming one fixed layout.
        data = _script(
            species_targets=((387, 248), (390, 249)),
            battles=(248, 249, 247),
        )

        families = parse_starter_branch_families(
            data, script_file_id=429, trainer_count=928
        )

        self.assertEqual(len(families), 1)
        family = families[0]
        self.assertEqual(family.selected, ((387, 248), (390, 249)))
        self.assertEqual(family.fallthrough_trainer_id, 247)

    def test_declines_a_script_that_never_reads_the_starter(self) -> None:
        data = _script(
            species_targets=((387, 248), (390, 249)),
            battles=(247, 248, 249),
            include_starter_read=False,
        )

        self.assertEqual(
            parse_starter_branch_families(data, script_file_id=1, trainer_count=928),
            (),
        )

    def test_declines_when_only_one_branch_resolves(self) -> None:
        data = _script(species_targets=((387, 248),), battles=(247, 248))

        self.assertEqual(
            parse_starter_branch_families(data, script_file_id=1, trainer_count=928),
            (),
        )

    def test_declines_when_one_value_selects_two_battles(self) -> None:
        # A value tested repeatedly is a scratch comparison, not a starter test.
        data = _script(
            species_targets=((20, 248), (20, 249)),
            battles=(247, 248, 249),
        )

        self.assertEqual(
            parse_starter_branch_families(data, script_file_id=1, trainer_count=928),
            (),
        )

    def test_declines_when_a_record_would_repeat(self) -> None:
        data = _script(
            species_targets=((387, 248), (390, 248)),
            battles=(247, 248),
        )

        self.assertEqual(
            parse_starter_branch_families(data, script_file_id=1, trainer_count=928),
            (),
        )

    def test_ignores_a_branch_that_misses_every_battle(self) -> None:
        # Only branches landing exactly on a battle count; this is what stops an
        # unrelated comparison from claiming a record.
        data = _script(
            species_targets=((387, 248), (390, 249)),
            battles=(247, 248, 249),
        )
        # Corrupt the second branch's relative offset so it points nowhere real.
        broken = bytearray(data)
        struct.pack_into("<i", broken, _HEADER + 4 + _BRANCH_SIZE + 5, 999)

        self.assertEqual(
            parse_starter_branch_families(
                bytes(broken), script_file_id=1, trainer_count=928
            ),
            (),
        )


class Gen4StarterSpeciesTests(unittest.TestCase):
    def test_decodes_word_sized_entries(self) -> None:
        data = struct.pack("<3I", 387, 390, 393)

        self.assertEqual(
            parse_starter_species(data, count=3, species_count=494), (387, 390, 393)
        )

    def test_rejects_a_wrongly_sized_region(self) -> None:
        with self.assertRaisesRegex(InvalidRomError, "has size 8; expected 12"):
            parse_starter_species(
                struct.pack("<2I", 387, 390), count=3, species_count=494
            )

    def test_rejects_values_that_are_not_species(self) -> None:
        with self.assertRaisesRegex(InvalidRomError, "invalid species"):
            parse_starter_species(
                struct.pack("<3I", 387, 9999, 393), count=3, species_count=494
            )

    def test_rejects_a_repeated_species(self) -> None:
        with self.assertRaisesRegex(InvalidRomError, "repeats a species"):
            parse_starter_species(
                struct.pack("<3I", 387, 387, 393), count=3, species_count=494
            )


class Gen4StarterBranchBlockTests(unittest.TestCase):
    def test_declines_block_resolution_without_a_starter_set(self) -> None:
        # Branches jump past the battles, so only block resolution could pair
        # them -- and that is withheld until the starter species are known.
        data = _script(
            species_targets=((387, 248), (390, 249)),
            battles=(247, 248, 249),
        )
        broken = bytearray(data)
        struct.pack_into("<i", broken, _HEADER + 4 + 5, 4)

        self.assertEqual(
            parse_starter_branch_families(
                bytes(broken), script_file_id=1, trainer_count=928
            ),
            (),
        )

    def test_ignores_a_comparison_value_that_is_not_a_starter(self) -> None:
        # Value 3 is a real species ID but not a starter; with the starter set
        # known it can no longer pose as one.
        data = _script(
            species_targets=((387, 248), (3, 249)),
            battles=(247, 248, 249),
        )

        self.assertEqual(
            parse_starter_branch_families(
                data,
                script_file_id=1,
                trainer_count=928,
                starter_species=(387, 390, 393),
            ),
            (),
        )


if __name__ == "__main__":
    unittest.main()

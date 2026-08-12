from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen4.dppt import parse_starter_branch_families
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


if __name__ == "__main__":
    unittest.main()

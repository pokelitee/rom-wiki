from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen5.shared.starter_branches import (
    parse_starter_branch_families,
    parse_starter_species,
)
from romwiki.util.errors import InvalidRomError

STARTERS = (495, 498, 501)


def _guard(index: int, trainer_id: int, *, skip: int, variable: int = 0x4030) -> bytes:
    """The stack-compare idiom BW uses to guard one starter's battle."""
    return (
        struct.pack("<HH", 0x0009, variable)  # StackPush(starter variable)
        + struct.pack("<HH", 0x0008, index)  # StackPushConst(starter index)
        + struct.pack("<HH", 0x0011, 1)  # StackCmp(equal)
        + struct.pack("<HBi", 0x001F, 0xFF, skip)  # VMJumpIf
        + struct.pack("<HHHH", 0x0085, trainer_id, 0, 1)  # CallTrainerBattle
    )


def _tag_guard(index: int, partner: int, *, skip: int) -> bytes:
    """A guarded tag battle: the starter selects the partner, not the foes."""
    return (
        struct.pack("<HH", 0x0009, 0x4030)
        + struct.pack("<HH", 0x0008, index)
        + struct.pack("<HH", 0x0011, 1)
        + struct.pack("<HBi", 0x001F, 0xFF, skip)
        + struct.pack("<HHHHH", 0x0086, partner, 342, 356, 0)  # Multi battle
    )


def _script(*functions: bytes) -> bytes:
    """A script whose function table points at each body in turn."""
    table_size = 4 * len(functions) + 2
    table = b""
    offset = table_size
    for index, body in enumerate(functions):
        cursor = index * 4
        table += struct.pack("<i", offset - (cursor + 4))
        offset += len(body)
    return table + struct.pack("<H", 0xFD13) + b"".join(functions)


_GUARD_SIZE = len(_guard(0, 1, skip=0))
_BATTLE = struct.pack("<HHHH", 0x0085, 3, 0, 1)
_HALT = struct.pack("<H", 0x0002)


def _group(ids, *, fallthrough: int | None) -> bytes:
    body = b""
    for offset, (index, trainer_id) in enumerate(ids):
        remaining = (len(ids) - offset - 1) * _GUARD_SIZE
        body += _guard(index, trainer_id, skip=remaining)
    if fallthrough is not None:
        body += struct.pack("<HHHH", 0x0085, fallthrough, 0, 1)
    return body


class Gen5StarterSpeciesTests(unittest.TestCase):
    def test_decodes_halfword_entries(self) -> None:
        data = struct.pack("<3H", *STARTERS)

        self.assertEqual(
            parse_starter_species(data, count=3, species_count=650), STARTERS
        )

    def test_rejects_a_wrongly_sized_region(self) -> None:
        with self.assertRaisesRegex(InvalidRomError, "has size 4; expected 6"):
            parse_starter_species(
                struct.pack("<2H", 495, 498), count=3, species_count=650
            )

    def test_rejects_values_that_are_not_species(self) -> None:
        with self.assertRaisesRegex(InvalidRomError, "invalid species"):
            parse_starter_species(
                struct.pack("<3H", 495, 9999, 501), count=3, species_count=650
            )

    def test_rejects_a_repeated_species(self) -> None:
        with self.assertRaisesRegex(InvalidRomError, "repeats a species"):
            parse_starter_species(
                struct.pack("<3H", 495, 495, 501), count=3, species_count=650
            )


class Gen5StarterBranchTests(unittest.TestCase):
    def _parse(self, *bodies: bytes, starter_species=STARTERS):
        return parse_starter_branch_families(
            _script(*bodies),
            script_file_id=782,
            trainer_count=615,
            starter_species=starter_species,
        )

    def test_decodes_index_to_record_and_the_fallthrough(self) -> None:
        families = self._parse(_group(((0, 53), (1, 54)), fallthrough=55) + _HALT)

        self.assertEqual(len(families), 1)
        family = families[0]
        self.assertEqual(family.selected, ((0, 53), (1, 54)))
        self.assertEqual(family.fallthrough_trainer_id, 55)
        self.assertEqual(family.position, 0)

    def test_splits_two_battle_sites_sharing_one_script(self) -> None:
        # Nuvema Town stages both rivals' opening battles in one script, and
        # they share the starter variable.
        families = self._parse(
            _group(((0, 59), (1, 60)), fallthrough=61) + _HALT,
            _group(((0, 53), (1, 54)), fallthrough=55) + _HALT,
        )

        self.assertEqual(len(families), 2)
        self.assertEqual(
            [f.trainer_ids for f in families], [(59, 60, 61), (53, 54, 55)]
        )
        self.assertEqual([f.position for f in families], [0, 1])

    def test_declines_without_a_starter_table(self) -> None:
        body = _group(((0, 53), (1, 54)), fallthrough=55) + _HALT

        self.assertEqual(self._parse(body, starter_species=None), ())

    def test_declines_a_single_guarded_branch(self) -> None:
        body = _group(((0, 53),), fallthrough=54) + _HALT

        self.assertEqual(self._parse(body), ())

    def test_ignores_an_index_outside_the_starter_table(self) -> None:
        body = _group(((0, 53), (7, 54)), fallthrough=55) + _HALT

        self.assertEqual(self._parse(body), ())

    def test_ignores_branches_on_any_other_variable(self) -> None:
        # Scratch variables compared with small constants select other things,
        # such as a rematch stage.
        skip = len(_guard(0, 1, skip=0))
        body = (
            _guard(0, 53, skip=skip, variable=0x8020)
            + _guard(1, 54, skip=0, variable=0x8020)
            + _BATTLE
            + _HALT
        )

        self.assertEqual(self._parse(body), ())

    def test_decodes_a_tag_battle_by_its_partner(self) -> None:
        size = len(_tag_guard(0, 1, skip=0))
        body = (
            _tag_guard(0, 588, skip=size)
            + _tag_guard(1, 589, skip=0)
            + struct.pack("<HHHHH", 0x0086, 590, 342, 356, 0)
            + _HALT
        )

        [family] = self._parse(body)

        self.assertEqual(family.selected, ((0, 588), (1, 589)))
        self.assertEqual(family.fallthrough_trainer_id, 590)


if __name__ == "__main__":
    unittest.main()

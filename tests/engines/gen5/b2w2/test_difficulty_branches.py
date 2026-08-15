from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen5.b2w2.difficulty_branches import (
    parse_difficulty_branch_families,
)


def _difficulty_script(
    normal_ids: tuple[int, ...],
    challenge_ids: tuple[int, ...],
    *,
    comparison: int = 1,
    battle_flags: int = 0,
) -> bytes:
    data = bytearray()
    data.extend(struct.pack("<HH", 0x2AF, 0x8001))  # GameGetDifficulty
    data.extend(struct.pack("<HH", 0x09, 0x8001))  # StackPush
    data.extend(struct.pack("<HH", 0x08, 2))  # StackPushConst
    data.extend(struct.pack("<HH", 0x11, comparison))  # StackCmp
    branch_offset = len(data)
    data.extend(struct.pack("<HBi", 0x1F, 0xFF, 0))  # VMJumpIf

    first_ids = challenge_ids if comparison == 1 else normal_ids
    second_ids = normal_ids if comparison == 1 else challenge_ids
    data.extend(_trainer_call(first_ids, flags=battle_flags))
    jump_offset = len(data)
    data.extend(struct.pack("<Hi", 0x1E, 0))  # VMJump
    second_offset = len(data)
    data.extend(_trainer_call(second_ids, flags=battle_flags))
    end_offset = len(data)
    data.extend(struct.pack("<H", 0x02))  # VMHalt

    struct.pack_into("<i", data, branch_offset + 3, second_offset - (branch_offset + 7))
    struct.pack_into("<i", data, jump_offset + 2, end_offset - (jump_offset + 6))
    return bytes(data)


def _trainer_call(trainer_ids: tuple[int, ...], *, flags: int = 0) -> bytes:
    if len(trainer_ids) <= 2:
        opponents = (*trainer_ids, *(0 for _ in range(2 - len(trainer_ids))))
        return struct.pack("<HHHH", 0x85, *opponents, flags)
    return struct.pack("<HHHHH", 0x86, *trainer_ids, flags)


class B2W2DifficultyBranchTests(unittest.TestCase):
    def test_decodes_normal_and_challenge_records_from_control_flow(self) -> None:
        families = parse_difficulty_branch_families(
            _difficulty_script((154,), (766,)),
            script_file_id=976,
            trainer_count=900,
        )

        self.assertEqual(len(families), 1)
        self.assertEqual(families[0].normal_trainer_ids, (154,))
        self.assertEqual(families[0].challenge_trainer_ids, (766,))

    def test_decodes_inverted_and_multi_trainer_selectors(self) -> None:
        families = parse_difficulty_branch_families(
            _difficulty_script((838, 839), (840, 841), comparison=0),
            script_file_id=930,
            trainer_count=900,
        )

        self.assertEqual(families[0].normal_trainer_ids, (838, 839))
        self.assertEqual(families[0].challenge_trainer_ids, (840, 841))

    def test_decodes_ally_and_opponents_from_a_multi_battle(self) -> None:
        families = parse_difficulty_branch_families(
            _difficulty_script((10, 11, 12), (20, 21, 22)),
            script_file_id=930,
            trainer_count=900,
        )

        self.assertEqual(families[0].normal_trainer_ids, (10, 11, 12))
        self.assertEqual(families[0].challenge_trainer_ids, (20, 21, 22))

    def test_ignores_a_selector_that_uses_the_same_records(self) -> None:
        families = parse_difficulty_branch_families(
            _difficulty_script((814,), (814,)),
            script_file_id=50,
            trainer_count=900,
        )

        self.assertEqual(families, ())

    def test_does_not_treat_battle_flags_as_a_trainer_id(self) -> None:
        families = parse_difficulty_branch_families(
            _difficulty_script((154,), (766,), battle_flags=7),
            script_file_id=976,
            trainer_count=900,
        )

        self.assertEqual(families[0].normal_trainer_ids, (154,))
        self.assertEqual(families[0].challenge_trainer_ids, (766,))


if __name__ == "__main__":
    unittest.main()

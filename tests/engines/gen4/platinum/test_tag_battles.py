from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen4.platinum.tag_battles import (
    parse_staged_partner_battle_families,
    parse_tag_battle_commands,
)
from tests.conftest import make_script

_HEADER = 6  # make_script's table: relative offset (4) + terminator (2)
_STARTER_VAR = 0x800C
_PARTNER_VAR = 0x8004
_GET_STARTER_SPECIES = 0x00DE
_GET_PLAYER_GENDER = 0x014D
_SET_VAR_FROM_VALUE = 0x0028
_COMPARE_VAR_TO_VALUE = 0x0011
_GOTO_IF = 0x001C
_CALL = 0x001A
_RETURN = 0x001B
_END = 0x0002
_START_TAG_BATTLE = 0x02A0


def _get_starter_species(var: int) -> bytes:
    return struct.pack("<HH", _GET_STARTER_SPECIES, var)


def _get_player_gender(var: int) -> bytes:
    return struct.pack("<HH", _GET_PLAYER_GENDER, var)


def _set_var(dest: int, value: int) -> bytes:
    return struct.pack("<HHH", _SET_VAR_FROM_VALUE, dest, value)


def _compare(var: int, value: int) -> bytes:
    return struct.pack("<HHH", _COMPARE_VAR_TO_VALUE, var, value)


def _goto_if(target: int, *, from_offset: int) -> bytes:
    relative_field = from_offset + 2 + 1
    relative = target - (relative_field + 4)
    return struct.pack("<HB", _GOTO_IF, 1) + struct.pack("<i", relative)


def _call(target: int, *, from_offset: int) -> bytes:
    relative_field = from_offset + 2
    relative = target - (relative_field + 4)
    return struct.pack("<H", _CALL) + struct.pack("<i", relative)


def _tag_battle(partner: int, enemy1: int, enemy2: int) -> bytes:
    return struct.pack(
        "<HHHH", _START_TAG_BATTLE, partner, enemy1, enemy2
    ) + struct.pack("<H", _END)


def _staged_subroutine(
    start: int, *, staged: list[tuple[int, int]], fallthrough_id: int
):
    """`staged` is [(species, trainer_id), ...]; returns (bytes, return_offset)."""
    body = _get_starter_species(_STARTER_VAR)
    offset = start + len(body)
    # Two passes: first compute total size to know the shared early-return
    # target, then re-emit with real GotoIf offsets.
    block_size = (
        len(_set_var(0, 0)) + len(_compare(0, 0)) + len(_goto_if(0, from_offset=0))
    )
    return_offset = offset + block_size * len(staged) + len(_set_var(0, 0))
    for species, trainer_id in staged:
        set_bytes = _set_var(_PARTNER_VAR, trainer_id)
        compare_bytes = _compare(_STARTER_VAR, species)
        goto_bytes = _goto_if(
            return_offset, from_offset=offset + len(set_bytes) + len(compare_bytes)
        )
        body += set_bytes + compare_bytes + goto_bytes
        offset += len(set_bytes) + len(compare_bytes) + len(goto_bytes)
    body += _set_var(_PARTNER_VAR, fallthrough_id)
    body += struct.pack("<H", _RETURN)
    assert start + len(body) - 2 == return_offset
    return body, return_offset


def _gender_gated_subroutine(
    start: int,
    *,
    gender_var: int,
    block_a: tuple[list[tuple[int, int]], int],
    block_b: tuple[list[tuple[int, int]], int],
) -> bytes:
    """`GetPlayerGender(G); Compare(G,0); GoToIf -> A; Compare(G,1); GoToIf -> B`.

    `A` and `B` are each an independent `_staged_subroutine` block, mirroring
    Platinum's Route 201 and Route 203 tag battles (the rival's own gender
    picks which nested starter-branch block runs).
    """
    header_prefix = _get_player_gender(gender_var)
    compare_len = len(_compare(0, 0))
    goto_len = len(_goto_if(0, from_offset=0))
    header_len = len(header_prefix) + 2 * (compare_len + goto_len)
    target_a = start + header_len
    a_bytes, _ = _staged_subroutine(
        target_a, staged=block_a[0], fallthrough_id=block_a[1]
    )
    target_b = target_a + len(a_bytes)
    b_bytes, _ = _staged_subroutine(
        target_b, staged=block_b[0], fallthrough_id=block_b[1]
    )

    goto_a_offset = start + len(header_prefix) + compare_len
    goto_b_offset = goto_a_offset + goto_len + compare_len
    body = (
        header_prefix
        + _compare(gender_var, 0)
        + _goto_if(target_a, from_offset=goto_a_offset)
        + _compare(gender_var, 1)
        + _goto_if(target_b, from_offset=goto_b_offset)
        + a_bytes
        + b_bytes
    )
    assert start + header_len == target_a
    return body


class Gen4TagBattleTests(unittest.TestCase):
    def test_extracts_literal_operands_tolerating_a_variable_slot(self) -> None:
        body = _tag_battle(_PARTNER_VAR, 200, 201)
        commands = parse_tag_battle_commands(make_script(body), trainer_count=1000)

        self.assertEqual(len(commands), 1)
        self.assertEqual(commands[0].trainer_ids, (200, 201))

    def test_extracts_all_three_when_fully_literal(self) -> None:
        body = _tag_battle(50, 200, 201)
        commands = parse_tag_battle_commands(make_script(body), trainer_count=1000)

        self.assertEqual(commands[0].trainer_ids, (50, 200, 201))

    def test_ignores_a_follow_on_that_is_not_a_real_command(self) -> None:
        body = struct.pack("<HHHHH", _START_TAG_BATTLE, _PARTNER_VAR, 200, 201, 0x9999)
        self.assertEqual(
            parse_tag_battle_commands(make_script(body), trainer_count=1000), ()
        )

    def test_resolves_staged_partner_via_call_then_return(self) -> None:
        sub, return_offset = _staged_subroutine(
            _HEADER,
            staged=[(387, 101), (390, 102)],
            fallthrough_id=103,
        )
        call_offset = _HEADER + len(sub)
        call_bytes = _call(_HEADER, from_offset=call_offset)
        tag_bytes = _tag_battle(_PARTNER_VAR, 200, 201)
        body = sub + call_bytes + tag_bytes

        families = parse_staged_partner_battle_families(
            make_script(body),
            script_file_id=7,
            trainer_count=1000,
            starter_species=(387, 390, 393),
        )

        self.assertEqual(len(families), 1)
        family = families[0]
        self.assertEqual(family.script_file_id, 7)
        self.assertEqual(sorted(family.selected), [(387, 101), (390, 102)])
        self.assertEqual(family.fallthrough_trainer_id, 103)

    def test_rejects_a_subroutine_gated_by_something_else_first(self) -> None:
        # A GetPlayerGender-style pre-check (or any opcode other than
        # GetPlayerStarterSpecies) before the staged blocks must not match:
        # this schema has no condition kind to represent the extra gate.
        unrelated = struct.pack("<HH", 0x004D, _STARTER_VAR)  # arbitrary opcode
        sub, _ = _staged_subroutine(
            _HEADER + len(unrelated),
            staged=[(387, 101), (390, 102)],
            fallthrough_id=103,
        )
        sub = unrelated + sub
        call_offset = _HEADER + len(sub)
        call_bytes = _call(_HEADER, from_offset=call_offset)
        tag_bytes = _tag_battle(_PARTNER_VAR, 200, 201)
        body = sub + call_bytes + tag_bytes

        families = parse_staged_partner_battle_families(
            make_script(body),
            script_file_id=7,
            trainer_count=1000,
            starter_species=(387, 390, 393),
        )

        self.assertEqual(families, ())

    def test_resolves_two_families_from_a_gender_gated_subroutine(self) -> None:
        # Platinum's Route 201 and Route 203 tag battles: the rival's own
        # gender picks which nested starter-branch block runs, so this must
        # resolve to two independent families -- one per gender branch --
        # rather than being silently dropped like an unrecognized gate.
        sub = _gender_gated_subroutine(
            _HEADER,
            gender_var=0x800C,
            block_a=([(387, 101), (390, 102)], 103),
            block_b=([(387, 201), (390, 202)], 203),
        )
        call_offset = _HEADER + len(sub)
        call_bytes = _call(_HEADER, from_offset=call_offset)
        tag_bytes = _tag_battle(_PARTNER_VAR, 200, 201)
        body = sub + call_bytes + tag_bytes

        families = parse_staged_partner_battle_families(
            make_script(body),
            script_file_id=9,
            trainer_count=1000,
            starter_species=(387, 390, 393),
        )

        self.assertEqual(len(families), 2)
        self.assertEqual(families[0].position, 0)
        self.assertEqual(sorted(families[0].selected), [(387, 101), (390, 102)])
        self.assertEqual(families[0].fallthrough_trainer_id, 103)
        self.assertEqual(families[1].position, 1)
        self.assertEqual(sorted(families[1].selected), [(387, 201), (390, 202)])
        self.assertEqual(families[1].fallthrough_trainer_id, 203)

    def test_ignores_a_literal_partner(self) -> None:
        tag_bytes = _tag_battle(50, 200, 201)
        families = parse_staged_partner_battle_families(
            make_script(tag_bytes),
            script_file_id=7,
            trainer_count=1000,
            starter_species=(387, 390, 393),
        )
        self.assertEqual(families, ())


if __name__ == "__main__":
    unittest.main()

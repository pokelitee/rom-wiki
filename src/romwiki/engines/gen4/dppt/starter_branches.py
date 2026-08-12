from __future__ import annotations

import struct
from dataclasses import dataclass

from romwiki.engines.gen4.dppt.scripts import (
    START_TRAINER_BATTLE,
    parse_script_table,
)

#: Reads the player's starter species into a script variable. This is the one
#: opcode this decoder has to know; which species the branches test, which
#: records they select, and which record is the fall-through are all read out of
#: the script itself.
GET_STARTER_SPECIES = 0x00DE

COMPARE_VAR_TO_VALUE = 0x0011
GOTO_IF = 0x001C

_SCRIPT_COMMAND_COUNT = 0x033A

# `GotoIf` is opcode(2) + condition(1) + relative offset(4). Relative offsets
# are measured from the end of their own field, the same convention the script
# table itself uses.
_GOTO_IF_RELATIVE_FIELD = 3
_RELATIVE_FIELD_SIZE = 4

# How far from the guarded battles a fall-through battle may sit. The branches
# and their shared fall-through are emitted as one contiguous block.
_FALLTHROUGH_WINDOW = 40


@dataclass(frozen=True, slots=True)
class Gen4StarterBranchFamily:
    """One starter-selected battle group, decoded from a single script file."""

    script_file_id: int
    #: starter species ID -> trainer ID, for branches that jump to a battle.
    selected: tuple[tuple[int, int], ...]
    #: the record reached when no branch is taken.
    fallthrough_trainer_id: int | None

    @property
    def trainer_ids(self) -> tuple[int, ...]:
        ids = [trainer_id for _, trainer_id in self.selected]
        if self.fallthrough_trainer_id is not None:
            ids.append(self.fallthrough_trainer_id)
        return tuple(ids)


def parse_starter_branch_families(
    data: bytes, *, script_file_id: int, trainer_count: int
) -> tuple[Gen4StarterBranchFamily, ...]:
    """Decode a script file's starter-selected battles.

    A family is only reported when the script reads the starter species and at
    least two comparisons against that variable each jump *directly* onto a
    literal battle command. That directness is what keeps this honest. The
    starter variable is the generic scratch variable, so it also carries
    unrelated comparisons; letting a branch claim a whole code block instead
    lets one of those unrelated values swallow a battle that belongs to the
    fall-through, which in Platinum's Pokémon League script produced a
    confident, wrong "Venusaur" branch. Requiring the jump to land on the
    battle itself declines those rather than guessing.

    Scripts that stage more than one battle per branch — the Survival Area
    pair — are therefore not resolved here, and are left unresolved rather
    than inferred.
    """
    try:
        code_offset = parse_script_table(data)
    except Exception:  # noqa: BLE001 - a script this decoder cannot walk is skipped
        return ()

    starter_vars = _starter_variables(data, code_offset)
    if not starter_vars:
        return ()

    battles = _literal_battles(data, code_offset, trainer_count)
    if not battles:
        return ()

    selected: dict[int, set[tuple[int, int]]] = {}
    for species, target, trainer_id in _guarded_branches(
        data, code_offset, battles, starter_vars
    ):
        selected.setdefault(species, set()).add((target, trainer_id))
    if len(selected) < 2:
        return ()
    # One value selecting two different battles is not a starter test.
    if any(len(targets) != 1 for targets in selected.values()):
        return ()

    resolved = {species: next(iter(targets)) for species, targets in selected.items()}
    targeted = {target for target, _ in resolved.values()}
    fallthrough = _fallthrough_battle(battles, targeted)
    trainer_ids = [trainer_id for _, trainer_id in resolved.values()]
    if fallthrough is not None:
        trainer_ids.append(fallthrough)
    if len(set(trainer_ids)) != len(trainer_ids):
        return ()

    return (
        Gen4StarterBranchFamily(
            script_file_id=script_file_id,
            selected=tuple(
                (species, trainer_id)
                for species, (_target, trainer_id) in sorted(resolved.items())
            ),
            fallthrough_trainer_id=fallthrough,
        ),
    )


def _starter_variables(data: bytes, code_offset: int) -> set[int]:
    return {
        struct.unpack_from("<H", data, offset + 2)[0]
        for offset in range(code_offset, len(data) - 3)
        if struct.unpack_from("<H", data, offset)[0] == GET_STARTER_SPECIES
    }


def _literal_battles(
    data: bytes, code_offset: int, trainer_count: int
) -> dict[int, int]:
    battles = {}
    for offset in range(code_offset, len(data) - 7):
        if struct.unpack_from("<H", data, offset)[0] != START_TRAINER_BATTLE:
            continue
        if struct.unpack_from("<H", data, offset + 6)[0] >= _SCRIPT_COMMAND_COUNT:
            continue
        trainer_id = struct.unpack_from("<H", data, offset + 2)[0]
        if 0 < trainer_id < trainer_count:
            battles[offset] = trainer_id
    return battles


def _guarded_branches(
    data: bytes,
    code_offset: int,
    battles: dict[int, int],
    starter_vars: set[int],
):
    limit = len(data) - (6 + _GOTO_IF_RELATIVE_FIELD + _RELATIVE_FIELD_SIZE)
    for offset in range(code_offset, limit):
        if struct.unpack_from("<H", data, offset)[0] != COMPARE_VAR_TO_VALUE:
            continue
        variable, value = struct.unpack_from("<HH", data, offset + 2)
        if variable not in starter_vars:
            continue
        if struct.unpack_from("<H", data, offset + 6)[0] != GOTO_IF:
            continue
        relative_field = offset + 6 + _GOTO_IF_RELATIVE_FIELD
        relative = struct.unpack_from("<i", data, relative_field)[0]
        target = relative_field + _RELATIVE_FIELD_SIZE + relative
        if target in battles:
            yield value, target, battles[target]


def _fallthrough_battle(battles: dict[int, int], targeted: set[int]) -> int | None:
    low, high = min(targeted), max(targeted)
    candidates = [
        trainer_id
        for offset, trainer_id in sorted(battles.items())
        if offset not in targeted
        and low - _FALLTHROUGH_WINDOW <= offset <= high + _FALLTHROUGH_WINDOW
    ]
    return candidates[0] if len(candidates) == 1 else None

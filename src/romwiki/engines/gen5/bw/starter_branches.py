from __future__ import annotations

import struct
from collections.abc import Sequence
from dataclasses import dataclass

from romwiki.engines.gen5.shared.script_disassembler import (
    Gen5Instruction,
    disassemble_script,
)
from romwiki.engines.gen5.shared.script_opcode_table import (
    STACK_CMP,
    STACK_CMP_EQUAL,
    STACK_PUSH,
    STACK_PUSH_CONST,
    VM_JUMP_IF,
)
from romwiki.util.errors import InvalidRomError

#: The stack-comparison idiom BW uses to branch on the player's starter:
#: push a variable, push a constant, compare for equality, then jump past the
#: guarded block when it does not match.
CALL_TRAINER_BATTLE = 0x0085

#: Starters are stored as species halfwords, one per starter index.
STARTER_SPECIES_ENTRY_SIZE = 2


@dataclass(frozen=True, slots=True)
class Gen5StarterBranchFamily:
    """One starter-selected battle group decoded from a single script file."""

    script_file_id: int
    #: Which battle site within the script this family describes.
    position: int
    #: starter index -> trainer ID, for branches that guard a battle.
    selected: tuple[tuple[int, int], ...]
    #: the record reached when no branch matches.
    fallthrough_trainer_id: int | None

    @property
    def trainer_ids(self) -> tuple[int, ...]:
        ids = [trainer_id for _, trainer_id in self.selected]
        if self.fallthrough_trainer_id is not None:
            ids.append(self.fallthrough_trainer_id)
        return tuple(ids)


def parse_starter_species(
    data: bytes, *, count: int, species_count: int
) -> tuple[int, ...]:
    """Decode the species each starter index selects.

    The values are validated as species rather than assumed: a region that does
    not hold `count` distinct in-range species is not this table.
    """
    expected = count * STARTER_SPECIES_ENTRY_SIZE
    if len(data) != expected:
        raise InvalidRomError(
            f"Gen V starter species table has size {len(data)}; expected {expected}"
        )
    species = struct.unpack(f"<{count}H", data)
    for value in species:
        if not 0 < value < species_count:
            raise InvalidRomError(
                f"Gen V starter species table contains invalid species {value}"
            )
    if len(set(species)) != len(species):
        raise InvalidRomError("Gen V starter species table repeats a species")
    return species


def parse_starter_branch_families(
    data: bytes,
    *,
    script_file_id: int,
    trainer_count: int,
    starter_species: Sequence[int] | None = None,
) -> tuple[Gen5StarterBranchFamily, ...]:
    """Decode a script file's starter-selected battles.

    BW branches on a starter *index* rather than a species: it pushes the
    starter variable and a constant, compares them, and jumps past the guarded
    block when they differ. `starter_species` bounds the valid indices and lets
    the resolver name them; without it nothing is reported, since an unbounded
    index cannot be told from an ordinary comparison.

    A group is only reported when at least two indices each guard a distinct
    literal battle, so a script that merely contains several battles yields
    nothing instead of a guess.
    """
    if not starter_species:
        return ()
    starter_count = len(starter_species)
    instructions = disassemble_script(data)
    if not instructions:
        return ()
    ordered = sorted(instructions, key=lambda value: value.offset)

    guards = _starter_guards(ordered, trainer_count, starter_count)
    if len(guards) < 2:
        return ()

    families = []
    for position, selected in enumerate(_guard_groups(guards)):
        fallthrough = _fallthrough_battle(ordered, selected, trainer_count)
        ids = [trainer_id for _, trainer_id in selected]
        if fallthrough is not None:
            ids.append(fallthrough)
        if len(set(ids)) != len(ids):
            continue
        families.append(
            Gen5StarterBranchFamily(
                script_file_id=script_file_id,
                position=position,
                selected=tuple(sorted(selected)),
                fallthrough_trainer_id=fallthrough,
            )
        )
    return tuple(families)


def _guard_groups(
    guards: Sequence[tuple[int, int, int, int]],
) -> list[list[tuple[int, int]]]:
    """Split guards into one group per battle site.

    A script can stage more than one starter-selected battle, and they share the
    starter variable -- Nuvema Town holds both rivals' opening battles. Grouping
    by variable alone merges them, so a group is closed when an index repeats or
    the variable changes, which is exactly where the next site begins.
    """
    groups: list[list[tuple[int, int]]] = []
    current: list[tuple[int, int]] = []
    current_variable: int | None = None
    for _offset, variable, index, trainer_id in sorted(guards):
        starts_new = variable != current_variable or any(
            index == seen for seen, _ in current
        )
        if starts_new and current:
            groups.append(current)
            current = []
        current_variable = variable
        current.append((index, trainer_id))
    if current:
        groups.append(current)
    return [group for group in groups if len(group) >= 2]


def _starter_guards(
    ordered: Sequence[Gen5Instruction], trainer_count: int, starter_count: int
) -> list[tuple[int, int, int, int]]:
    """(offset, variable, starter index, trainer ID) for each guarded battle."""
    guards = []
    for position in range(len(ordered) - 4):
        window = ordered[position : position + 5]
        opcodes = [instruction.opcode for instruction in window]
        if opcodes != [
            STACK_PUSH,
            STACK_PUSH_CONST,
            STACK_CMP,
            VM_JUMP_IF,
            CALL_TRAINER_BATTLE,
        ]:
            continue
        if window[2].params[0] != STACK_CMP_EQUAL:
            continue
        variable = window[0].params[0]
        index = window[1].params[0]
        trainer_id = window[4].params[0]
        if not 0 <= index < starter_count:
            continue
        if not 0 < trainer_id < trainer_count:
            continue
        guards.append((window[0].offset, variable, index, trainer_id))
    return guards


def _fallthrough_battle(
    ordered: Sequence[Gen5Instruction],
    selected: Sequence[tuple[int, int]],
    trainer_count: int,
) -> int | None:
    """The battle reached once every starter branch has been skipped.

    It is the first battle after the last guarded one that is not itself
    guarded, which is how the final starter is handled: the script stops
    testing and simply falls into it.
    """
    guarded = {trainer_id for _, trainer_id in selected}
    battles = [
        instruction
        for instruction in ordered
        if instruction.opcode == CALL_TRAINER_BATTLE
        and 0 < instruction.params[0] < trainer_count
    ]
    last_guarded = max(
        (i for i, b in enumerate(battles) if b.params[0] in guarded), default=None
    )
    if last_guarded is None:
        return None
    for battle in battles[last_guarded + 1 :]:
        if battle.params[0] not in guarded:
            return battle.params[0]
    return None

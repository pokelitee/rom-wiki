from __future__ import annotations

import struct
from dataclasses import dataclass

from .disassembler import Gen5Instruction, disassemble_function
from .opcode_table import GAME_GET_DIFFICULTY

_DIFFICULTY_SELECTOR_PREFIX = struct.pack("<H", GAME_GET_DIFFICULTY)
_SELECTOR_NAMES = (
    "GameGetDifficulty",
    "VMStackPush",
    "VMStackPushConst",
    "VMStackCmp",
    "VMJumpIf",
)
_TRAINER_BATTLE_COMMANDS = {"CallTrainerBattle", "CallTrainerMultiBattle"}
_TERMINATORS = {"VMHalt", "VMReturn"}
_BRANCHES = {"VMJump", "VMJumpIf"}


@dataclass(frozen=True, slots=True)
class DifficultyBranchFamily:
    script_file_id: int
    position: int
    normal_trainer_ids: tuple[int, ...]
    challenge_trainer_ids: tuple[int, ...]


def parse_difficulty_branch_families(
    data: bytes, *, script_file_id: int, trainer_count: int
) -> tuple[DifficultyBranchFamily, ...]:
    """Decode literal trainer records selected by B2W2 difficulty mode.

    Field scripts call ``GameGetDifficulty``, compare its result with mode 2
    (Challenge Mode), and branch to exact trainer-battle commands. Following
    both control-flow arms avoids inferring relationships from record IDs,
    names, archive adjacency, or party similarity.
    """
    families = []
    position = 0
    while True:
        position = data.find(_DIFFICULTY_SELECTOR_PREFIX, position)
        if position < 0:
            break
        instructions = disassemble_function(data, position)
        family = _parse_selector(
            instructions,
            script_file_id=script_file_id,
            position=position,
            trainer_count=trainer_count,
        )
        if family is not None:
            families.append(family)
        position += len(_DIFFICULTY_SELECTOR_PREFIX)
    return tuple(families)


def _parse_selector(
    instructions: dict[int, Gen5Instruction],
    *,
    script_file_id: int,
    position: int,
    trainer_count: int,
) -> DifficultyBranchFamily | None:
    selector = _instruction_chain(instructions, position, len(_SELECTOR_NAMES))
    if tuple(instruction.name for instruction in selector) != _SELECTOR_NAMES:
        return None
    get_difficulty, push, mode, comparison, branch = selector
    if (
        push.params != get_difficulty.params
        or mode.params != (2,)
        or comparison.params not in {(0,), (1,)}
        or len(branch.params) != 2
    ):
        return None

    fallthrough = _reachable_offsets(instructions, branch.next_offset)
    branch_target = branch.next_offset + branch.params[-1]
    targeted = _reachable_offsets(instructions, branch_target)
    shared = fallthrough & targeted
    fallthrough_ids = _trainer_ids(
        instructions, fallthrough - shared, trainer_count=trainer_count
    )
    targeted_ids = _trainer_ids(
        instructions, targeted - shared, trainer_count=trainer_count
    )

    # StackCmp 1 is the equality form used by normal B2W2 scripts: a true
    # mode-2 comparison falls through to Challenge Mode. StackCmp 0 inverts
    # that test, as used by Redux's Bianca selector.
    normal_ids, challenge_ids = (
        (targeted_ids, fallthrough_ids)
        if comparison.params == (1,)
        else (fallthrough_ids, targeted_ids)
    )
    if (
        not normal_ids
        or not challenge_ids
        or normal_ids == challenge_ids
        or len(normal_ids) != len(challenge_ids)
    ):
        return None
    return DifficultyBranchFamily(
        script_file_id=script_file_id,
        position=position,
        normal_trainer_ids=normal_ids,
        challenge_trainer_ids=challenge_ids,
    )


def _instruction_chain(
    instructions: dict[int, Gen5Instruction], start: int, count: int
) -> tuple[Gen5Instruction, ...]:
    chain = []
    offset = start
    for _ in range(count):
        instruction = instructions.get(offset)
        if instruction is None:
            break
        chain.append(instruction)
        offset = instruction.next_offset
    return tuple(chain)


def _reachable_offsets(
    instructions: dict[int, Gen5Instruction], start: int
) -> set[int]:
    reached: set[int] = set()
    pending = [start]
    while pending:
        offset = pending.pop()
        if offset in reached or offset not in instructions:
            continue
        reached.add(offset)
        pending.extend(_successors(instructions[offset], instructions))
    return reached


def _successors(
    instruction: Gen5Instruction, instructions: dict[int, Gen5Instruction]
) -> tuple[int, ...]:
    if instruction.name in _TERMINATORS:
        return ()
    successors = []
    if instruction.name != "VMJump" and instruction.next_offset in instructions:
        successors.append(instruction.next_offset)
    if instruction.name in _BRANCHES:
        target = instruction.next_offset + instruction.params[-1]
        if target in instructions:
            successors.append(target)
    return tuple(successors)


def _trainer_ids(
    instructions: dict[int, Gen5Instruction],
    offsets: set[int],
    *,
    trainer_count: int,
) -> tuple[int, ...]:
    battle_commands = [
        instructions[offset]
        for offset in sorted(offsets)
        if instructions[offset].name in _TRAINER_BATTLE_COMMANDS
    ]
    if len(battle_commands) != 1:
        return ()

    trainer_ids = []
    instruction = battle_commands[0]
    trainer_params = (
        instruction.params[:2]
        if instruction.name == "CallTrainerBattle"
        else instruction.params[:3]
    )
    for trainer_id in trainer_params:
        if 0 < trainer_id < trainer_count and trainer_id not in trainer_ids:
            trainer_ids.append(trainer_id)
    return tuple(trainer_ids)

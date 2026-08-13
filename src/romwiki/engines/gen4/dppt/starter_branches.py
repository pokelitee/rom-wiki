from __future__ import annotations

import struct
from collections.abc import Sequence
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
    #: Which staged battle inside each branch block this family describes.
    position: int
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
    data: bytes,
    *,
    script_file_id: int,
    trainer_count: int,
    starter_species: Sequence[int] | None = None,
) -> tuple[Gen4StarterBranchFamily, ...]:
    """Decode a script file's starter-selected battles.

    The starter variable is also the engine's general-purpose scratch variable,
    so a comparison against it is not by itself a starter test. `starter_species`
    — decoded from the game's own starter accessor — is what separates the two.
    Without it, only branches jumping *directly* onto a literal battle are
    trusted, because that directness is the sole remaining guard; with it, a
    branch may also select a block of staged battles, since an unrelated
    comparison value can no longer pose as a starter.

    That distinction is not theoretical: resolving blocks without the species
    check let the value `3` claim a battle belonging to the fall-through in
    Platinum's Pokémon League script, publishing a confident, wrong "Venusaur"
    branch.
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

    branches = _starter_branches(data, code_offset, starter_vars)
    if starter_species is not None:
        branches = [branch for branch in branches if branch[0] in set(starter_species)]
    if len({species for species, _ in branches}) < 2:
        return ()

    # A branch landing on the battle itself is the strongest evidence, and it is
    # stable across hacks that pack extra battles into the same script. Block
    # resolution is only reached where that finds nothing, and only when the
    # decoded starter set makes it safe.
    blocks = _resolve_blocks(branches, battles, trusted=False)
    if blocks is None and starter_species is not None:
        blocks = _resolve_blocks(branches, battles, trusted=True)
    if blocks is None:
        return ()

    staged_count = len(next(iter(blocks.values())))
    if any(len(staged) != staged_count for staged in blocks.values()):
        return ()

    fallthrough = _fallthrough_staged(battles, blocks, branches)
    if fallthrough is not None and len(fallthrough) != staged_count:
        return ()

    families = []
    for position in range(staged_count):
        selected = tuple(
            sorted((species, staged[position]) for species, staged in blocks.items())
        )
        fallthrough_id = fallthrough[position] if fallthrough else None
        ids = [trainer_id for _, trainer_id in selected]
        if fallthrough_id is not None:
            ids.append(fallthrough_id)
        if len(set(ids)) != len(ids):
            return ()
        families.append(
            Gen4StarterBranchFamily(
                script_file_id=script_file_id,
                position=position,
                selected=selected,
                fallthrough_trainer_id=fallthrough_id,
            )
        )
    return tuple(families)


def _resolve_blocks(
    branches: list[tuple[int, int]],
    battles: dict[int, int],
    *,
    trusted: bool,
) -> dict[int, list[int]] | None:
    """Map each starter species to the records its branch selects."""
    boundaries = sorted({target for _, target in branches})
    blocks: dict[int, list[int]] = {}
    for species, target in branches:
        if trusted:
            staged = _battles_in_block(battles, target, boundaries)
        else:
            staged = [battles[target]] if target in battles else []
        if not staged:
            # A starter branch may guard code that stages no battle at all; that
            # says nothing about the branches that do.
            continue
        if species in blocks and blocks[species] != staged:
            # The same starter reaching two different sets of records is not the
            # simple selection this decoder claims to understand.
            return None
        blocks[species] = staged
    return blocks if len(blocks) >= 2 else None


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


def _starter_branches(
    data: bytes, code_offset: int, starter_vars: set[int]
) -> list[tuple[int, int]]:
    """Every `CompareVarToValue` on a starter variable paired with its jump."""
    limit = len(data) - (6 + _GOTO_IF_RELATIVE_FIELD + _RELATIVE_FIELD_SIZE)
    branches = []
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
        if code_offset <= target < len(data):
            branches.append((value, target))
    return branches


def _block_end(target: int, boundaries: list[int], limit: int) -> int:
    """A block runs until the next branch target, so blocks never overlap."""
    return next((value for value in boundaries if value > target), limit)


def _battles_in_block(
    battles: dict[int, int], target: int, boundaries: list[int]
) -> list[int]:
    end = _block_end(target, boundaries, max(battles) + 1)
    return [
        trainer_id
        for offset, trainer_id in sorted(battles.items())
        if target <= offset < end
    ]


def _fallthrough_staged(
    battles: dict[int, int],
    blocks: dict[int, list[int]],
    branches: list[tuple[int, int]],
) -> list[int] | None:
    """Records reached when no starter branch is taken.

    The fall-through block is not always laid out before the branches it backs:
    Renegade Platinum emits it last where retail emits it first, so this looks
    either side of the branched region rather than assuming an order.
    """
    claimed = {trainer_id for staged in blocks.values() for trainer_id in staged}
    offsets = [offset for offset, tid in battles.items() if tid in claimed]
    if not offsets:
        return None
    low, high = min(offsets), max(offsets)
    window = _FALLTHROUGH_WINDOW * max(1, len(blocks))
    staged = [
        trainer_id
        for offset, trainer_id in sorted(battles.items())
        if trainer_id not in claimed and low - window <= offset <= high + window
    ]
    return staged or None

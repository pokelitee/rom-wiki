"""Facts read from disassembled Generation III event scripts.

Each fact is one literal command, not an inference. pret's macros
(`asm/macros/event.inc`) define the command shapes:

- `finditem` / `giveitem` set `VAR_0x8000` (item) and `VAR_0x8001`
  (quantity) with `setorcopyvar`, then `callstd STD_FIND_ITEM` (an item
  ball) or `callstd STD_OBTAIN_ITEM` (an item an NPC hands over).
- `setwildbattle species, level, item` stages a static encounter, as does
  `seteventmon` for event legendaries: `setvar` of `VAR_0x8004` (species),
  `VAR_0x8005` (level), and `VAR_0x8006` (item), then the
  `CreateEnemyEventMon` special, whose number each leaf supplies.
- FireRed/LeafGreen's `giveitem_msg` gives an item with `additem item,
  amount`.
- `givemon species, level, item` and `giveegg species` give a Pokémon.
- `pokemart products` opens a mart whose products are a u16 item list
  ending in 0.
- A trader's script sets `VAR_0x8008` to the trade's index and calls the
  `GetInGameTradeSpeciesInfo` special (number supplied by each leaf).

`setorcopyvar` copies another variable when its value is a variable ID
(0x4000 and up), so only literal values below that count.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from romwiki.engines.common.script_control_flow import ScriptInstruction
from romwiki.util.errors import InvalidRomError

from .pointers import resolve_gba_pointer
from .scripts import TRAINER_BATTLE

SET_OR_COPY_VAR = 0x1A
SET_VAR = 0x16
SPECIAL = 0x25
SPECIAL_VAR = 0x26
COPY_VAR = 0x19
COMPARE_VAR_TO_VALUE = 0x21
GOTO_IF = 0x06
CALL_IF = 0x07
GOTO = 0x05
CALL = 0x04
ADD_ITEM = 0x44
CALL_STD = 0x09
STD_OBTAIN_ITEM = 0
STD_FIND_ITEM = 1
GIVE_MON = 0x79
GIVE_EGG = 0x7A
POKEMART = 0x86
SET_WILD_BATTLE = 0xB6
_ITEM_VAR = 0x8000
_QUANTITY_VAR = 0x8001
_EVENT_MON_VARS = (0x8004, 0x8005, 0x8006)
_TRADE_VAR = 0x8008
# `switch` copies its value into `VAR_0x8000`; a menu's choice is `VAR_RESULT`.
_SWITCH_VAR = 0x8000
_RESULT_VAR = 0x800D
_COST_VAR = 0x8008
_EQUAL = 1
# How far a menu's selector can sit before its `switch`.
_MENU_SEARCH_LIMIT = 32
# How far a branch target can sit before its battle, and how deep to follow
# calls and jumps to reach it.
_BATTLE_SEARCH_LIMIT = 60
_BATTLE_SEARCH_DEPTH = 3
_FIRST_VAR_ID = 0x4000
_MAX_LEVEL = 100
# Generous bound on a mart's product list.
_MAX_MART_ITEMS = 64


@dataclass(frozen=True, slots=True)
class ScriptItem:
    item_id: int
    quantity: int
    offset: int


@dataclass(frozen=True, slots=True)
class ScriptPokemon:
    kind: str
    species_id: int
    level: int | None
    held_item_id: int | None
    offset: int


@dataclass(frozen=True, slots=True)
class ScriptMart:
    item_ids: tuple[int, ...]
    offset: int


def find_item_ball(
    instructions: Mapping[int, ScriptInstruction],
) -> ScriptItem | None:
    """The item an object's script finds, if it is a `finditem` item ball."""
    items = _std_items(instructions, STD_FIND_ITEM)
    return items[0] if items else None


def find_given_items(
    instructions: Mapping[int, ScriptInstruction],
) -> tuple[ScriptItem, ...]:
    """Every literal `giveitem` and `additem` in the scripts."""
    added = tuple(
        ScriptItem(instruction.params[0], instruction.params[1], address)
        for address, instruction in sorted(instructions.items())
        if instruction.opcode == ADD_ITEM
        and 0 < instruction.params[0] < _FIRST_VAR_ID
        and 0 < instruction.params[1] < _FIRST_VAR_ID
    )
    return tuple(
        sorted(
            (*_std_items(instructions, STD_OBTAIN_ITEM), *added),
            key=lambda item: item.offset,
        )
    )


def find_pokemon(
    instructions: Mapping[int, ScriptInstruction],
    *,
    species_count: int,
    event_mon_special: int,
) -> tuple[ScriptPokemon, ...]:
    """Every literal `setwildbattle`, `seteventmon`, `givemon`, and
    `giveegg`.
    """
    found = list(_event_mons(instructions, species_count, event_mon_special))
    for address in sorted(instructions):
        instruction = instructions[address]
        opcode, params = instruction.opcode, instruction.params
        if opcode in (SET_WILD_BATTLE, GIVE_MON):
            species_id, level, item_id = params[0], params[1], params[2]
            if 0 < species_id < species_count and 0 < level <= _MAX_LEVEL:
                found.append(
                    ScriptPokemon(
                        "static" if opcode == SET_WILD_BATTLE else "pokemon",
                        species_id,
                        level,
                        item_id or None,
                        address,
                    )
                )
        elif opcode == GIVE_EGG and 0 < params[0] < species_count:
            found.append(ScriptPokemon("egg", params[0], None, None, address))
    return tuple(sorted(found, key=lambda pokemon: pokemon.offset))


def _event_mons(
    instructions: Mapping[int, ScriptInstruction],
    species_count: int,
    special: int,
) -> tuple[ScriptPokemon, ...]:
    found = []
    for address in sorted(instructions):
        run = [instructions[address]]
        while len(run) < 4 and run[-1].next_offset in instructions:
            run.append(instructions[run[-1].next_offset])
        if len(run) < 4 or run[3].opcode != SPECIAL or run[3].params[0] != special:
            continue
        if any(
            step.opcode != SET_VAR or step.params[0] != variable
            for step, variable in zip(run, _EVENT_MON_VARS, strict=False)
        ):
            continue
        species_id, level, item_id = (step.params[1] for step in run[:3])
        if 0 < species_id < species_count and 0 < level <= _MAX_LEVEL:
            found.append(
                ScriptPokemon(
                    "static", species_id, level, item_id or None, run[3].offset
                )
            )
    return tuple(found)


def find_marts(
    instructions: Mapping[int, ScriptInstruction],
    read: Callable[[int, int], bytes],
) -> tuple[ScriptMart, ...]:
    """Every `pokemart` and its product list."""
    marts = []
    for address in sorted(instructions):
        instruction = instructions[address]
        if instruction.opcode != POKEMART:
            continue
        try:
            offset = resolve_gba_pointer(instruction.params[0])
            data = read(offset, _MAX_MART_ITEMS * 2 + 2)
        except InvalidRomError:
            continue
        items: list[int] = []
        for index in range(0, len(data), 2):
            item_id = int.from_bytes(data[index : index + 2], "little")
            if item_id == 0:
                marts.append(ScriptMart(tuple(items), address))
                break
            items.append(item_id)
    return tuple(marts)


def _std_items(
    instructions: Mapping[int, ScriptInstruction], std: int
) -> tuple[ScriptItem, ...]:
    # `instructions` is keyed by address, so each command's successor is
    # found through its `next_offset`.
    found = []
    for address in sorted(instructions):
        first = instructions[address]
        second = instructions.get(first.next_offset)
        third = instructions.get(second.next_offset) if second else None
        if (
            second is not None
            and third is not None
            and _sets(first, _ITEM_VAR)
            and _sets(second, _QUANTITY_VAR)
            and third.opcode == CALL_STD
            and third.params[0] == std
        ):
            found.append(ScriptItem(first.params[1], second.params[1], third.offset))
    return tuple(found)


def _sets(instruction: ScriptInstruction, variable: int) -> bool:
    return (
        instruction.opcode == SET_OR_COPY_VAR
        and instruction.params[0] == variable
        and 0 < instruction.params[1] < _FIRST_VAR_ID
    )


def find_trades(
    instructions: Mapping[int, ScriptInstruction],
    *,
    trade_count: int,
    trade_info_special: int,
) -> tuple[tuple[int, int], ...]:
    """`(trade index, command address)` for each trade the scripts offer."""
    if not any(
        instruction.opcode in (SPECIAL, SPECIAL_VAR)
        and instruction.params[-1] == trade_info_special
        for instruction in instructions.values()
    ):
        return ()
    return tuple(
        (instruction.params[1], address)
        for address, instruction in sorted(instructions.items())
        if instruction.opcode == SET_VAR
        and instruction.params[0] == _TRADE_VAR
        and instruction.params[1] < trade_count
    )


def find_menu_costs(
    instructions: Mapping[int, ScriptInstruction], *, selector_var: int
) -> dict[tuple[int, int], int]:
    """`(menu, choice) -> cost` for Emerald's Battle Frontier tutors.

    Each tutor sets `selector_var` to its menu (0 or 1), shows the menu, and
    `switch`es on the choice: each `case` compares `VAR_0x8000` with the
    choice and jumps to a block that sets `VAR_0x8008` to the cost in
    Battle Points (pret's `BattleFrontier_Lounge7` scripts).
    """
    costs: dict[tuple[int, int], int] = {}
    for address in sorted(instructions):
        selector = instructions[address]
        if selector.opcode != SET_VAR or selector.params[0] != selector_var:
            continue
        cursor = instructions.get(selector.next_offset)
        for _ in range(_MENU_SEARCH_LIMIT):
            if cursor is None or (
                cursor.opcode == COPY_VAR
                and cursor.params == (_SWITCH_VAR, _RESULT_VAR)
            ):
                break
            cursor = instructions.get(cursor.next_offset)
        case = instructions.get(cursor.next_offset) if cursor else None
        while (
            case is not None
            and case.opcode == COMPARE_VAR_TO_VALUE
            and case.params[0] == _SWITCH_VAR
        ):
            jump = instructions.get(case.next_offset)
            if jump is None or jump.opcode != GOTO_IF or jump.params[0] != _EQUAL:
                break
            target = instructions.get(jump.params[1])
            if (
                target is not None
                and target.opcode == SET_VAR
                and target.params[0] == _COST_VAR
            ):
                costs[(selector.params[1], case.params[1])] = target.params[1]
            case = instructions.get(jump.next_offset)
    return costs


def find_starter_branches(
    instructions: Mapping[int, ScriptInstruction], *, starter_var: int
) -> tuple[tuple[tuple[int, int], ...], ...]:
    """Each starter-dependent battle as `((starter value, trainer), ...)`.

    A rival's script compares `starter_var` with each value and jumps or
    calls to a block that starts that party's `trainerbattle`. FireRed/
    LeafGreen compare the variable directly (`call_if_eq`); Emerald
    `switch`es on it, copying it into `VAR_0x8000` first. Each run of
    consecutive comparisons is one battle.
    """
    previous = {
        instruction.next_offset: instruction for instruction in instructions.values()
    }
    branches = []
    consumed: set[int] = set()
    for address in sorted(instructions):
        compare = instructions[address]
        if address in consumed or compare.opcode != COMPARE_VAR_TO_VALUE:
            continue
        variable = compare.params[0]
        before = previous.get(address)
        if not (
            variable == starter_var
            or (
                variable == _SWITCH_VAR
                and before is not None
                and before.opcode == COPY_VAR
                and before.params == (_SWITCH_VAR, starter_var)
            )
        ):
            continue
        choices = []
        cursor: ScriptInstruction | None = compare
        while (
            cursor is not None
            and cursor.opcode == COMPARE_VAR_TO_VALUE
            and cursor.params[0] == variable
        ):
            consumed.add(cursor.offset)
            branch = instructions.get(cursor.next_offset)
            if branch is None or branch.opcode not in (GOTO_IF, CALL_IF):
                break
            if branch.params[0] == _EQUAL:
                trainer = _first_battle(instructions, branch.params[1], 0)
                if trainer is not None:
                    choices.append((cursor.params[1], trainer))
            cursor = instructions.get(branch.next_offset)
        if choices:
            branches.append(tuple(choices))
    return tuple(branches)


def find_starter_species(
    instructions: Mapping[int, ScriptInstruction], *, starter_var: int
) -> dict[int, int]:
    """`starter value -> species` from FireRed/LeafGreen's starter scripts.

    The confirming script copies the chosen ball's number into
    `starter_var` and gives the species held in another variable; each
    ball's script sets the number and then the species.
    """
    numbers = {
        instruction.params[1]
        for instruction in instructions.values()
        if instruction.opcode == COPY_VAR and instruction.params[0] == starter_var
    }
    species_vars = {
        instruction.params[0]
        for instruction in instructions.values()
        if instruction.opcode == GIVE_MON and instruction.params[0] >= _FIRST_VAR_ID
    }
    species: dict[int, int] = {}
    for instruction in instructions.values():
        if instruction.opcode != SET_VAR or instruction.params[0] not in numbers:
            continue
        following = instructions.get(instruction.next_offset)
        if (
            following is not None
            and following.opcode == SET_VAR
            and following.params[0] in species_vars
        ):
            species[instruction.params[1]] = following.params[1]
    return species


def _first_battle(
    instructions: Mapping[int, ScriptInstruction], address: int, depth: int
) -> int | None:
    for _ in range(_BATTLE_SEARCH_LIMIT):
        instruction = instructions.get(address)
        if instruction is None:
            return None
        if instruction.opcode == TRAINER_BATTLE:
            return int(instruction.params[1])
        if instruction.opcode in (CALL, GOTO) and depth < _BATTLE_SEARCH_DEPTH:
            found = _first_battle(instructions, instruction.params[0], depth + 1)
            if found is not None or instruction.opcode == GOTO:
                return found
        address = instruction.next_offset
    return None

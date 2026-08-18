from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from romwiki.engines.gen4.script_disassembler import (
    Gen4Instruction,
    disassemble_function,
)
from romwiki.engines.gen4.script_table import parse_script_function_offsets

# Some NPC gifts and custom shops don't call the literal `AddItem` opcode
# directly; instead they stage the item and quantity into two scratch work
# variables and hand off to one of the field engine's common-script give-item
# routines via `CallCommonScript`. Verified against real ROM data in
# Renegade Platinum: `2044` is a direct NPC gift (Floaroma Town's "Item
# Fanatic", six species-conditional held-item grants, all six matched
# exactly against the hack's own changelog) and `2016` is a paid shop
# purchase (the Route 208 "Rare Berry Seller" and Snowpoint City "Evolution
# Item Seller" custom shops, 12 and 10 items respectively, both matched
# exactly). Sacred Gold/Storm Silver confirm the same convention under a
# different ID (`2033`, verified against Sprout Tower's TM70 gift).
#
# Platinum and HeartGold/SoulSilver are cousins, not siblings sharing one
# ARM9 codebase the way Black/White and Black 2/White 2 do, so their
# `CallCommonScript` ID tables are assigned independently and a numeric ID
# confirmed for one is not assumed safe for the other -- each engine leaf
# supplies its own confirmed set (see `gen4/dppt/script_items.py` and
# `gen4/hgss/script_items.py`) rather than sharing one constant here.
#
# Unlike Gen5's equivalent convention, these aren't simple one-arm scripts:
# an NPC offering a choice of items (by species, or from a shop menu) sets
# the item register differently in each mutually-exclusive branch and then
# jumps to ONE shared call site, so a single fixed-distance "nearest
# preceding write" check only ever finds the one arm textually closest to
# the call and silently drops every other choice. Resolving this correctly
# means walking the script's own control flow *forward* from each literal
# item write to see which give-item call(s) it can actually reach before
# being overwritten by a later write to the same register -- see
# `_reachable_common_script_calls` below.
#
# The literal write itself uses either `SetVarFromValue` or `SetVarFromVar`
# depending on which game compiled the script -- verified against Sacred
# Gold, whose own script compiler emits `SetVarFromVar` for what is, in
# every observed case, still a bare literal operand (`SetVarFromVar`'s own
# second operand never once fell in this ROM's real variable-ID range,
# 32768+, across the whole script archive; every occurrence was a small
# literal-shaped value instead). Accepting both opcodes is safe rather than
# a guess: a genuine variable reference would fail the item/quantity bounds
# check in `_record` below just as reliably as an unrelated literal would.
_ITEM_WRITE_COMMANDS = frozenset({"SetVarFromValue", "SetVarFromVar"})
_ITEM_WORK_VARIABLE = 32772
_QUANTITY_WORK_VARIABLE = 32773
_GOTO = "GoTo"
_GOTO_IF = "GoToIf"
_CALL = "Call"
_CALL_IF = "CallIf"
_TERMINAL_COMMANDS = frozenset({"End", "Return", "ReturnCommonScript"})


@dataclass(frozen=True, slots=True)
class ScriptAwardedItem:
    item_id: int
    quantity: int
    command_offset: int
    command: str


def find_script_awarded_items(
    data: bytes, *, item_count: int, give_item_common_script_ids: frozenset[int]
) -> tuple[ScriptAwardedItem, ...]:
    """Return reachable item-grant commands whose item and quantity are literals.

    Covers both the direct `AddItem` opcode and the indirect
    `SetVarFromValue`/`SetVarFromVar` + `CallCommonScript` give-item
    convention (see module docstring above). Catches item grants an NPC's
    own dialogue script hands over directly (e.g. a species-conditional
    gift, or a custom shop's purchase), which never place an item-ball/
    hidden-item event on the map and so are otherwise invisible to location
    extraction.

    `give_item_common_script_ids` is the confirmed set of `CallCommonScript`
    targets that are real give-item routines for this specific engine leaf
    -- `CallCommonScript` is a general-purpose call to any of the engine's
    global subroutines, so accepting every target would match unrelated
    common scripts en masse.
    """
    awards: dict[tuple[int, int], ScriptAwardedItem] = {}
    for function_offset in parse_script_function_offsets(data):
        instructions = disassemble_function(data, function_offset)
        by_offset = {
            instr.offset: instr
            for instr in sorted(instructions.values(), key=lambda value: value.offset)
        }
        for instruction in by_offset.values():
            if instruction.name == "AddItem":
                item_id, quantity, _result = instruction.params
                _record(awards, instruction, item_id, quantity, item_count)
                continue
            if instruction.name not in _ITEM_WRITE_COMMANDS:
                continue
            variable, item_id = instruction.params
            if variable != _ITEM_WORK_VARIABLE:
                continue
            baseline_quantity = _nearest_preceding_quantity(
                by_offset, instruction.offset
            )
            for call, quantity in _reachable_common_script_calls(
                by_offset, instruction, baseline_quantity, give_item_common_script_ids
            ):
                _record(awards, call, item_id, quantity, item_count)
    return tuple(awards[key] for key in sorted(awards))


def _record(
    awards: dict[tuple[int, int], ScriptAwardedItem],
    call: Gen4Instruction,
    item_id: int,
    quantity: int | None,
    item_count: int,
) -> None:
    if quantity is None:
        return
    if not 0 < item_id < item_count:
        return
    if not 0 < quantity <= 999:
        return
    awards[(call.offset, item_id)] = ScriptAwardedItem(
        item_id=item_id,
        quantity=quantity,
        command_offset=call.offset,
        command=call.name,
    )


def _nearest_preceding_quantity(
    by_offset: dict[int, Gen4Instruction], before_offset: int
) -> int | None:
    """The quantity in effect when a given item write begins its own arm.

    A shop or gift script often sets the quantity once and reuses it across
    several sequential item choices, so the quantity active at any one
    choice may have been set earlier in the script, not within its own arm.
    """
    quantity = None
    for instruction in by_offset.values():
        if instruction.offset >= before_offset:
            break
        if (
            instruction.name in _ITEM_WRITE_COMMANDS
            and instruction.params[0] == _QUANTITY_WORK_VARIABLE
        ):
            quantity = instruction.params[1]
    return quantity


def _successors(instruction: Gen4Instruction) -> tuple[int, ...]:
    if instruction.name == _GOTO:
        return (instruction.next_offset + instruction.params[-1],)
    if instruction.name in (_GOTO_IF, _CALL_IF, _CALL):
        return (
            instruction.next_offset,
            instruction.next_offset + instruction.params[-1],
        )
    if instruction.name in _TERMINAL_COMMANDS:
        return ()
    return (instruction.next_offset,)


def _reachable_common_script_calls(
    by_offset: dict[int, Gen4Instruction],
    item_write: Gen4Instruction,
    baseline_quantity: int | None,
    give_item_common_script_ids: Iterable[int],
) -> list[tuple[Gen4Instruction, int | None]]:
    """Walk forward from one literal item write to the calls it actually feeds.

    A path stops (without reporting) the moment it re-writes the item
    register -- that value belongs to a later, independent arm, resolved by
    its own call to this function -- so a shared convergence point after a
    branch never misattributes one arm's item to another's.
    """
    calls: list[tuple[Gen4Instruction, int | None]] = []
    visited: set[int] = set()
    worklist = [(offset, baseline_quantity) for offset in _successors(item_write)]
    while worklist:
        offset, quantity = worklist.pop()
        if offset in visited or offset not in by_offset:
            continue
        visited.add(offset)
        instruction = by_offset[offset]
        if instruction.name in _ITEM_WRITE_COMMANDS:
            variable, value = instruction.params
            if variable == _ITEM_WORK_VARIABLE:
                continue
            if variable == _QUANTITY_WORK_VARIABLE:
                quantity = value
        elif (
            instruction.name == "CallCommonScript"
            and instruction.params[0] in give_item_common_script_ids
        ):
            calls.append((instruction, quantity))
        worklist.extend((successor, quantity) for successor in _successors(instruction))
    return calls


__all__ = ["ScriptAwardedItem", "find_script_awarded_items"]

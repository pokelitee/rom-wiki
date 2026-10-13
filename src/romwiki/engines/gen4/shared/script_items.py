from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from romwiki.engines.gen4.shared.script_disassembler import (
    Gen4Instruction,
    disassemble_function,
)
from romwiki.engines.gen4.shared.script_opcode_table import OPCODE_TABLE
from romwiki.engines.gen4.shared.script_table import parse_script_function_offsets

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
# supplies its own confirmed set (see `gen4/platinum/script_items.py` and
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
#
# These are Platinum's own opcode *names* (from `gen4/script_opcode_table.py`,
# the pret/pokeplatinum-derived default `opcode_table`) -- HeartGold/SoulSilver
# renumbers and renames several of these same-shaped commands (its own table,
# from pret/pokeheartgold, calls the identical two-operand literal-write
# opcode `SetVar` and the var-to-var copy `CopyVar`/`SetOrCopyVar`, and its
# `CallCommonScript` equivalent `CallStd` -- verified against real Sacred
# Gold ROM bytes: `SetVar(32772, 397)`, `SetVar(32773, 1)`, `CallStd(2033)`
# is the exact real byte sequence for the documented Sprout Tower TM70 grant,
# not `SetVarFromVar`/`CallCommonScript`, which HGSS's real opcode table
# never produces). `gen4/hgss/script_items.py` supplies its own name set and
# opcode table accordingly; do not assume Platinum's names transfer.
_ITEM_WRITE_COMMANDS = frozenset({"SetVarFromValue", "SetVarFromVar"})
_ITEM_WORK_VARIABLE = 32772
_QUANTITY_WORK_VARIABLE = 32773
_GOTO = "GoTo"
_GOTO_IF = "GoToIf"
_CALL = "Call"
_CALL_IF = "CallIf"
_TERMINAL_COMMANDS = frozenset({"End", "Return", "ReturnCommonScript"})
_CALL_COMMON_SCRIPT_COMMAND = "CallCommonScript"


@dataclass(frozen=True, slots=True)
class ScriptAwardedItem:
    item_id: int
    quantity: int
    command_offset: int
    command: str


def find_script_awarded_items(
    data: bytes,
    *,
    item_count: int,
    give_item_common_script_ids: frozenset[int],
    opcode_table: dict[int, tuple[str, tuple[int, ...]]] = OPCODE_TABLE,
    item_write_commands: frozenset[str] = _ITEM_WRITE_COMMANDS,
    call_common_script_command: str = _CALL_COMMON_SCRIPT_COMMAND,
    terminal_commands: frozenset[str] = _TERMINAL_COMMANDS,
) -> tuple[ScriptAwardedItem, ...]:
    """Return reachable item-grant commands whose item and quantity are literals.

    Covers both the direct `AddItem` opcode and the indirect literal-write +
    common-script-call give-item convention (see module docstring above).
    Catches item grants an NPC's own dialogue script hands over directly
    (e.g. a species-conditional gift, or a custom shop's purchase), which
    never place an item-ball/hidden-item event on the map and so are
    otherwise invisible to location extraction.

    `give_item_common_script_ids` is the confirmed set of common-script-call
    targets that are real give-item routines for this specific engine leaf
    -- the underlying opcode is a general-purpose call to any of the
    engine's global subroutines, so accepting every target would match
    unrelated common scripts en masse. `opcode_table`, `item_write_commands`,
    `call_common_script_command`, and `terminal_commands` default to
    Platinum's own opcode table and instruction names; other engine leaves
    (e.g. HeartGold/SoulSilver, whose opcode numbering and instruction names
    differ -- see module docstring) must supply their own.
    """
    awards: dict[tuple[int, int], ScriptAwardedItem] = {}
    for function_offset in parse_script_function_offsets(data):
        instructions = disassemble_function(
            data, function_offset, opcode_table=opcode_table
        )
        by_offset = {
            instr.offset: instr
            for instr in sorted(instructions.values(), key=lambda value: value.offset)
        }
        for instruction in by_offset.values():
            if instruction.name == "AddItem":
                item_id, quantity, _result = instruction.params
                _record(awards, instruction, item_id, quantity, item_count)
                continue
            if instruction.name not in item_write_commands:
                continue
            variable, item_id = instruction.params
            if variable != _ITEM_WORK_VARIABLE:
                continue
            baseline_quantity = _nearest_preceding_quantity(
                by_offset, instruction.offset, item_write_commands
            )
            for call, call_quantity in _reachable_common_script_calls(
                by_offset,
                instruction,
                baseline_quantity,
                give_item_common_script_ids,
                item_write_commands=item_write_commands,
                call_common_script_command=call_common_script_command,
                terminal_commands=terminal_commands,
            ):
                _record(awards, call, item_id, call_quantity, item_count)
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
    by_offset: dict[int, Gen4Instruction],
    before_offset: int,
    item_write_commands: frozenset[str],
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
            instruction.name in item_write_commands
            and instruction.params[0] == _QUANTITY_WORK_VARIABLE
        ):
            quantity = instruction.params[1]
    return quantity


def _successors(
    instruction: Gen4Instruction, terminal_commands: frozenset[str]
) -> tuple[int, ...]:
    if instruction.name == _GOTO:
        return (instruction.next_offset + instruction.params[-1],)
    if instruction.name in (_GOTO_IF, _CALL_IF, _CALL):
        return (
            instruction.next_offset,
            instruction.next_offset + instruction.params[-1],
        )
    if instruction.name in terminal_commands:
        return ()
    return (instruction.next_offset,)


def _reachable_common_script_calls(
    by_offset: dict[int, Gen4Instruction],
    item_write: Gen4Instruction,
    baseline_quantity: int | None,
    give_item_common_script_ids: Iterable[int],
    *,
    item_write_commands: frozenset[str],
    call_common_script_command: str,
    terminal_commands: frozenset[str],
) -> list[tuple[Gen4Instruction, int | None]]:
    """Walk forward from one literal item write to the calls it actually feeds.

    A path stops (without reporting) the moment it re-writes the item
    register -- that value belongs to a later, independent arm, resolved by
    its own call to this function -- so a shared convergence point after a
    branch never misattributes one arm's item to another's.
    """
    calls: list[tuple[Gen4Instruction, int | None]] = []
    visited: set[int] = set()
    worklist = [
        (offset, baseline_quantity)
        for offset in _successors(item_write, terminal_commands)
    ]
    while worklist:
        offset, quantity = worklist.pop()
        if offset in visited or offset not in by_offset:
            continue
        visited.add(offset)
        instruction = by_offset[offset]
        if instruction.name in item_write_commands:
            variable, value = instruction.params
            if variable == _ITEM_WORK_VARIABLE:
                continue
            if variable == _QUANTITY_WORK_VARIABLE:
                quantity = value
        elif (
            instruction.name == call_common_script_command
            and instruction.params[0] in give_item_common_script_ids
        ):
            calls.append((instruction, quantity))
        worklist.extend(
            (successor, quantity)
            for successor in _successors(instruction, terminal_commands)
        )
    return calls


__all__ = ["ScriptAwardedItem", "find_script_awarded_items"]

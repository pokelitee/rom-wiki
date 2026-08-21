from __future__ import annotations

from dataclasses import dataclass

from romwiki.engines.gen5.shared.script_disassembler import (
    Gen5Instruction,
    disassemble_script,
)

# Some NPC-dialogue item grants don't call the literal `ItemAdd` opcode
# directly; instead they stage the item and quantity into two scratch work
# variables and hand off to one of the engine's global give-item routines via
# `RTCallGlobal`. Verified against real ROM data in both BW and B2W2: this
# exact `WorkSet`+`WorkSet`+`RTCallGlobal` shape with these two registers is
# the real give-item convention, confirmed against BW's own documented NPC
# gifts (Choice Specs at Relic Castle -> 2805, RageCandyBar at Driftveil City
# -> 2805, Life Orb at Chargestone Cave -> 2805, Choice Scarf at Cold Storage
# -> 2805, Cherish Ball x20 at the Nimbasa gate -> 2805, Metronome at Route 13
# -> 2807) and B2W2's TM40/Lunar Wing gifts (-> 2814).
#
# `RTCallGlobal` is a general-purpose call to *any* of the engine's global
# subroutines, most of which have nothing to do with items and pass unrelated
# arguments through these same two scratch registers by pure calling
# convention -- so the global function ID itself, not just the register
# shape, must be checked, or this matches unrelated calls en masse (verified:
# scanning every `RTCallGlobal` regardless of target ID pulls in dozens of
# clearly-unrelated common/shared scripts across many locations). ID 10110 was
# checked and explicitly ruled out this way -- it recurs with implausible
# arguments, item 0, in an unrelated tutorial script.
_GIVE_ITEM_GLOBAL_FUNCTION_IDS = frozenset({2805, 2806, 2807, 2814})
_ITEM_WORK_VARIABLE = 32768
_QUANTITY_WORK_VARIABLE = 32769


@dataclass(frozen=True, slots=True)
class ScriptAwardedItem:
    item_id: int
    quantity: int
    command_offset: int
    command: str


def find_script_awarded_items(
    data: bytes, *, item_count: int
) -> tuple[ScriptAwardedItem, ...]:
    """Return reachable item-grant commands whose item and quantity are literals.

    Covers both the direct `ItemAdd` opcode and the indirect
    `WorkSet`+`WorkSet`+`RTCallGlobal` give-item convention (see module
    docstring above).
    """
    instructions = disassemble_script(data)
    preceding_by_offset = {
        instruction.next_offset: instruction for instruction in instructions
    }
    awards = []
    for instruction in instructions:
        if instruction.name == "ItemAdd":
            item_id, quantity, _result = instruction.params
        elif (
            instruction.name == "RTCallGlobal"
            and instruction.params[0] in _GIVE_ITEM_GLOBAL_FUNCTION_IDS
        ):
            preceding_item_id, preceding_quantity = _preceding_item_grant_literals(
                instruction, preceding_by_offset
            )
            if preceding_item_id is None or preceding_quantity is None:
                continue
            item_id, quantity = preceding_item_id, preceding_quantity
        else:
            continue
        if not 0 < item_id < item_count:
            continue
        if not 0 < quantity <= 999:
            continue
        awards.append(
            ScriptAwardedItem(
                item_id=item_id,
                quantity=quantity,
                command_offset=instruction.offset,
                command=instruction.name,
            )
        )
    return tuple(awards)


def _preceding_item_grant_literals(
    instruction: Gen5Instruction,
    preceding_by_offset: dict[int, Gen5Instruction],
) -> tuple[int | None, int | None]:
    set_quantity = preceding_by_offset.get(instruction.offset)
    if set_quantity is None or set_quantity.name != "WorkSet":
        return None, None
    set_item = preceding_by_offset.get(set_quantity.offset)
    if set_item is None or set_item.name != "WorkSet":
        return None, None
    if set_item.params[0] != _ITEM_WORK_VARIABLE:
        return None, None
    if set_quantity.params[0] != _QUANTITY_WORK_VARIABLE:
        return None, None
    return set_item.params[1], set_quantity.params[1]


__all__ = ["ScriptAwardedItem", "find_script_awarded_items"]

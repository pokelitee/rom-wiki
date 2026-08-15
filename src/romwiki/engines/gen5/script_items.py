from __future__ import annotations

from dataclasses import dataclass

from romwiki.engines.gen5.script_disassembler import disassemble_script


@dataclass(frozen=True, slots=True)
class ScriptAwardedItem:
    item_id: int
    quantity: int
    command_offset: int
    command: str


def find_script_awarded_items(
    data: bytes, *, item_count: int
) -> tuple[ScriptAwardedItem, ...]:
    """Return reachable ItemAdd commands whose item and quantity are literals."""
    awards = []
    for instruction in disassemble_script(data):
        if instruction.name != "ItemAdd":
            continue
        item_id, quantity, _result = instruction.params
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


__all__ = ["ScriptAwardedItem", "find_script_awarded_items"]

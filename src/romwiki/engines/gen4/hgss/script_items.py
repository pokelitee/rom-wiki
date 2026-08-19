from __future__ import annotations

from romwiki.engines.gen4.hgss.script_opcode_table import OPCODE_TABLE
from romwiki.engines.gen4.script_items import ScriptAwardedItem as ScriptAwardedItem
from romwiki.engines.gen4.script_items import (
    find_script_awarded_items as _find_script_awarded_items,
)

# Verified against real Sacred Gold data: Sprout Tower's second floor NPC
# gives TM70 via `SetVar(32772, 397)` + `SetVar(32773, 1)` + `CallStd(2033)`
# -- confirmed as the real byte sequence (not Platinum's differently-named
# `SetVarFromVar`/`CallCommonScript`) by disassembling with HGSS's own
# opcode table directly against the real Sacred Gold ROM's script archive
# (`a/0/1/2`); 397 is TM70's own real item ID. `CallStd` shares opcode 0x14
# with Platinum's `CallCommonScript` (same number, different pret-project
# naming) -- the same give-item-by-ID convention, not a different mechanism.
_GIVE_ITEM_COMMON_SCRIPT_IDS = frozenset({2033})

# HGSS's own opcode table renumbers/renames these relative to Platinum's
# (see `gen4/script_items.py`'s module docstring): the literal/var-copy
# write pair is `SetVar`/`CopyVar` (not `SetVarFromValue`/`SetVarFromVar`),
# the common-script call is `CallStd` (not `CallCommonScript`), and the
# common-script return is `RestartCurrentScript` (not `ReturnCommonScript`).
_ITEM_WRITE_COMMANDS = frozenset({"SetVar", "CopyVar"})
_CALL_COMMON_SCRIPT_COMMAND = "CallStd"
_TERMINAL_COMMANDS = frozenset({"End", "Return", "RestartCurrentScript"})


def find_script_awarded_items(
    data: bytes, *, item_count: int
) -> tuple[ScriptAwardedItem, ...]:
    return _find_script_awarded_items(
        data,
        item_count=item_count,
        give_item_common_script_ids=_GIVE_ITEM_COMMON_SCRIPT_IDS,
        opcode_table=OPCODE_TABLE,
        item_write_commands=_ITEM_WRITE_COMMANDS,
        call_common_script_command=_CALL_COMMON_SCRIPT_COMMAND,
        terminal_commands=_TERMINAL_COMMANDS,
    )


__all__ = ["ScriptAwardedItem", "find_script_awarded_items"]

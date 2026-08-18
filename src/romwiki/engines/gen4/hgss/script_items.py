from __future__ import annotations

from romwiki.engines.gen4.script_items import ScriptAwardedItem as ScriptAwardedItem
from romwiki.engines.gen4.script_items import (
    find_script_awarded_items as _find_script_awarded_items,
)

# Verified against real Sacred Gold data: Sprout Tower's second floor NPC
# gives TM70 via `SetVarFromVar(32772, 397)` + `SetVarFromVar(32773, 1)` +
# `CallCommonScript(2033)`, and 397 is TM70's own real item ID.
_GIVE_ITEM_COMMON_SCRIPT_IDS = frozenset({2033})


def find_script_awarded_items(
    data: bytes, *, item_count: int
) -> tuple[ScriptAwardedItem, ...]:
    return _find_script_awarded_items(
        data,
        item_count=item_count,
        give_item_common_script_ids=_GIVE_ITEM_COMMON_SCRIPT_IDS,
    )


__all__ = ["ScriptAwardedItem", "find_script_awarded_items"]

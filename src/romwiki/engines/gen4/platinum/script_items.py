from __future__ import annotations

from romwiki.engines.gen4.shared.script_items import (
    ScriptAwardedItem as ScriptAwardedItem,
)
from romwiki.engines.gen4.shared.script_items import (
    find_script_awarded_items as _find_script_awarded_items,
)

from .script_opcode_table import OPCODE_TABLE

# Verified against real Renegade Platinum data -- see `gen4/script_items.py`'s
# module docstring for the two confirmed grants this ID set covers.
_GIVE_ITEM_COMMON_SCRIPT_IDS = frozenset({2016, 2044})


def find_script_awarded_items(
    data: bytes, *, item_count: int
) -> tuple[ScriptAwardedItem, ...]:
    return _find_script_awarded_items(
        data,
        item_count=item_count,
        give_item_common_script_ids=_GIVE_ITEM_COMMON_SCRIPT_IDS,
        opcode_table=OPCODE_TABLE,
    )


__all__ = ["ScriptAwardedItem", "find_script_awarded_items"]

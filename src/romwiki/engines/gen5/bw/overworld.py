from __future__ import annotations

from romwiki.engines.gen5.shared.trainer_records import (
    resolve_common_script_trainer_id as resolve_common_script_trainer_id,
)

COMMON_SCRIPT_MEMBER_BASE = 442
_COMMON_SCRIPT_REFERENCE_BASE = 10000


def resolve_common_script_member(script_used: int, *, member_count: int) -> int | None:
    """Resolve a 10xxx overworld script reference to its archive member."""
    if script_used < _COMMON_SCRIPT_REFERENCE_BASE:
        return None
    member = COMMON_SCRIPT_MEMBER_BASE + script_used - _COMMON_SCRIPT_REFERENCE_BASE
    return member if member < member_count else None

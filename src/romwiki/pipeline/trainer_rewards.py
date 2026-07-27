from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from romwiki.engines.registry import GEN5_BW_ENGINE


def calculate_base_prize_money(
    trainer: Mapping[str, Any], *, engine: str
) -> dict[str, Any] | None:
    """Return an exact, engine-neutral base payout when all inputs are known."""
    if engine != GEN5_BW_ENGINE:
        return None

    party = trainer.get("party")
    multiplier = trainer.get("victory_money_multiplier")
    if not party or not isinstance(multiplier, int) or multiplier <= 0:
        return None

    final_level = party[-1].get("level")
    if not isinstance(final_level, int) or final_level <= 0:
        return None

    base_factor = 4
    return {
        "amount": final_level * multiplier * base_factor,
        "final_party_level": final_level,
        "multiplier": multiplier,
        "base_factor": base_factor,
    }

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from romwiki.engines.registry import get_engine
from romwiki.util.errors import DataSourceError


def calculate_base_prize_money(
    trainer: Mapping[str, Any], *, engine: str
) -> dict[str, Any] | None:
    """Return an exact, engine-neutral base payout when all inputs are known."""
    try:
        trainer_format = get_engine(engine).formats.trainers
    except DataSourceError:
        return None

    party = trainer.get("party")
    multiplier = trainer.get("victory_money_multiplier")
    if not party or not isinstance(multiplier, int) or multiplier <= 0:
        return None

    final_level = party[-1].get("level")
    if not isinstance(final_level, int) or final_level <= 0:
        return None

    base_factor = 4
    battle_format_multiplier = (
        2 if trainer_format == "class-gender" and trainer.get("double_battle") else 1
    )
    multiplier_provenance = trainer.get("victory_money_multiplier_provenance")
    if multiplier_provenance is None and trainer_format == "battle-mode":
        record_provenance = trainer.get("provenance", {})
        if record_provenance.get("archive") is not None:
            multiplier_provenance = {
                "source": "rom",
                "archive": record_provenance["archive"],
                "member": record_provenance.get("member"),
                "offset": 17,
            }
    return {
        "amount": final_level * multiplier * base_factor * battle_format_multiplier,
        "final_party_level": final_level,
        "multiplier": multiplier,
        "base_factor": base_factor,
        "battle_format_multiplier": battle_format_multiplier,
        "multiplier_provenance": multiplier_provenance,
    }

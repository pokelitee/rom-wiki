"""B2W2-specific trainer selection and location behavior."""

from romwiki.engines.gen5.bw.overworld import (
    parse_overworld_npcs,
)
from romwiki.engines.gen5.bw.scripts import (
    CHECK_TRAINER_BATTLE_WON,
    START_TRAINER_BATTLE,
    START_TRAINER_MULTI_BATTLE,
    Gen5TrainerBattleCommand,
    parse_trainer_battle_commands,
)
from romwiki.engines.gen5.bw.trainers import (
    TRAINER_RECORD_SIZE,
    parse_trainer_record,
)


def resolve_common_script_trainer_id(script_used: int, *, trainer_count: int) -> None:
    """Do not apply BW's Black-validated common-script arithmetic to B2W2."""
    return None


__all__ = [
    "CHECK_TRAINER_BATTLE_WON",
    "Gen5TrainerBattleCommand",
    "START_TRAINER_BATTLE",
    "START_TRAINER_MULTI_BATTLE",
    "TRAINER_RECORD_SIZE",
    "parse_overworld_npcs",
    "parse_trainer_battle_commands",
    "parse_trainer_record",
    "resolve_common_script_trainer_id",
]

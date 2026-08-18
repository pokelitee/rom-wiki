"""B2W2-specific trainer selection and location behavior."""

from romwiki.engines.gen5.b2w2.overworld import (
    parse_overworld_npcs,
)
from romwiki.engines.gen5.b2w2.scripts import (
    CHECK_TRAINER_BATTLE_WON,
    START_TRAINER_BATTLE,
    START_TRAINER_MULTI_BATTLE,
    Gen5TrainerBattleCommand,
    parse_trainer_battle_commands,
)
from romwiki.engines.gen5.trainer_records import (
    TRAINER_RECORD_SIZE,
    parse_trainer_record,
    resolve_common_script_trainer_id,
)


def trainer_name_index(trainer_id: int) -> int:
    """Return B2W2's message index, whose table retains entry zero."""
    return trainer_id


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
    "trainer_name_index",
]

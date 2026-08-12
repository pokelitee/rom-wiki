from romwiki.engines.gen5.trainer_records import (
    TRAINER_RECORD_SIZE,
    TRAINER_RECORD_SIZE_WITHOUT_VICTORY_ITEM,
    parse_trainer_record,
)


def trainer_name_index(trainer_id: int) -> int:
    """Return BW's zero-based message index for a one-based trainer ID."""
    return trainer_id - 1


__all__ = [
    "TRAINER_RECORD_SIZE",
    "TRAINER_RECORD_SIZE_WITHOUT_VICTORY_ITEM",
    "parse_trainer_record",
    "trainer_name_index",
]

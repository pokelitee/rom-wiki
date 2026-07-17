from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from romwiki.schema.pokemon import RecordProvenance


@dataclass(frozen=True, slots=True)
class TrainerPokemon:
    difficulty: int
    gender_ability: int
    level: int
    species_id: int
    form_id: int
    held_item_id: int | None
    move_ids: tuple[int, ...]
    ball_seal: int


@dataclass(frozen=True, slots=True)
class Gen4Trainer:
    trainer_id: int
    name: str
    class_id: int
    class_name: str
    has_custom_moves: bool
    has_held_items: bool
    unknown_byte: int
    party_count: int
    reward_item_ids: tuple[int, int, int, int]
    ai_flags: int
    double_battle: bool
    party: tuple[TrainerPokemon, ...]
    trailing_party_data: bytes
    provenance: RecordProvenance
    party_provenance: RecordProvenance

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["trailing_party_data"] = self.trailing_party_data.hex()
        return result

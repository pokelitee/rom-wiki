from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal, TypedDict

from romwiki.schema.pokemon import RecordProvenance


class TrainerAttribute(TypedDict):
    """A stored or derived party attribute with explicit provenance."""

    source: Literal["stored", "derived", "engine-default"]


class NormalizedTrainerPokemon(TypedDict):
    """Engine-neutral party fields consumed by enrichment and renderers."""

    species_id: int
    form_id: int
    level: int
    held_item_id: int | None
    move_ids: list[int]
    moves_source: Literal["explicit", "level-up", "unavailable"]
    ability: TrainerAttribute | None
    nature: TrainerAttribute | None
    gender: TrainerAttribute | None
    ivs: TrainerAttribute | None
    evs: TrainerAttribute | None
    calculated_stats: TrainerAttribute | None
    source_fields: dict[str, Any]


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
class TrainerLocation:
    header_id: int
    internal_name: str
    location_name_id: int
    name: str
    event_file_id: int
    object_index: int
    object_local_id: int
    script_id: int
    trainer_type: int
    x: int
    y: int
    z: int


@dataclass(frozen=True, slots=True)
class TrainerScriptReference:
    header_id: int
    internal_name: str
    location_name_id: int
    name: str
    script_file_id: int
    command_offset: int
    opponent_slot: int


@dataclass(frozen=True, slots=True)
class Gen4Trainer:
    trainer_id: int
    name: str
    class_id: int
    class_name: str
    class_gender: Literal["male", "female"]
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
    locations: tuple[TrainerLocation, ...] = ()
    script_references: tuple[TrainerScriptReference, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["trailing_party_data"] = self.trailing_party_data.hex()
        return result

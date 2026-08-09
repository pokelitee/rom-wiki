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
class AbilitySlotTrainerPokemon:
    difficulty: int
    ability_slot: int
    forced_gender_flag: int
    level: int
    species_id: int
    form_id: int
    held_item_id: int | None
    move_ids: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class BattleModeTrainer:
    trainer_id: int
    name: str
    class_id: int
    class_name: str
    # 0=single, 1=double, 2=triple, 3=rotation (Gen5RomHandler.java's own
    # comment on the Trainer Data record) -- unlike Generation IV's
    # single/double-only battle_type.
    battle_mode: int
    double_battle: bool
    has_custom_moves: bool
    has_held_items: bool
    party_count: int
    reward_item_ids: tuple[int, int, int, int]
    ai_flags: int
    healer: bool
    victory_money_multiplier: int
    victory_item_id: int
    party: tuple[AbilitySlotTrainerPokemon, ...]
    provenance: RecordProvenance
    party_provenance: RecordProvenance
    locations: tuple[TrainerLocation, ...] = ()
    script_references: tuple[TrainerScriptReference, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ClassGenderTrainer:
    trainer_id: int
    name: str
    class_id: int
    class_name: str
    class_gender: Literal["male", "female"]
    victory_money_multiplier: int | None
    has_custom_moves: bool
    has_held_items: bool
    unknown_byte: int
    party_count: int
    reward_item_ids: tuple[int, int, int, int]
    ai_flags: int
    battle_type: int
    double_battle: bool
    party: tuple[TrainerPokemon, ...]
    trailing_party_data: bytes
    provenance: RecordProvenance
    party_provenance: RecordProvenance
    locations: tuple[TrainerLocation, ...] = ()
    script_references: tuple[TrainerScriptReference, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        if self.victory_money_multiplier is None:
            result.pop("victory_money_multiplier")
        result["trailing_party_data"] = self.trailing_party_data.hex()
        return result

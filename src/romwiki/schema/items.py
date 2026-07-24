from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from romwiki.schema.pokemon import RecordProvenance


@dataclass(frozen=True, slots=True)
class ItemPartyEffects:
    heal_sleep: bool
    heal_poison: bool
    heal_burn: bool
    heal_freeze: bool
    heal_paralysis: bool
    heal_confusion: bool
    heal_attract: bool
    guard_spec: bool
    revive: bool
    revive_all: bool
    level_up: bool
    evolve: bool
    attack_stages: int
    defense_stages: int
    special_attack_stages: int
    special_defense_stages: int
    speed_stages: int
    accuracy_stages: int
    critical_hit_stages: int
    pp_up: bool
    pp_max: bool
    pp_restore: bool
    pp_restore_all: bool
    hp_restore: bool
    hp_ev: bool
    attack_ev: bool
    defense_ev: bool
    speed_ev: bool
    special_attack_ev: bool
    special_defense_ev: bool
    friendship_low: bool
    friendship_medium: bool
    friendship_high: bool
    hp_ev_amount: int
    attack_ev_amount: int
    defense_ev_amount: int
    speed_ev_amount: int
    special_attack_ev_amount: int
    special_defense_ev_amount: int
    hp_restored: int
    pp_restored: int
    friendship_low_amount: int
    friendship_medium_amount: int
    friendship_high_amount: int


@dataclass(frozen=True, slots=True)
class Gen4Item:
    item_id: int
    data_archive_member: int
    price: int
    hold_effect_id: int
    hold_effect_parameter: int
    pluck_effect_id: int
    fling_effect_id: int
    fling_power: int
    natural_gift_power: int
    natural_gift_type_id: int
    prevent_toss: bool
    selectable: bool
    field_pocket_id: int
    battle_pocket_mask: int
    field_use_function_id: int
    battle_use_function_id: int
    party_use: bool
    party_effects: ItemPartyEffects
    provenance: RecordProvenance

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class Gen5Item:
    item_id: int
    data_archive_member: int
    price: int
    hold_effect_id: int
    pluck_effect_id: int
    fling_effect_id: int
    fling_power: int
    provenance: RecordProvenance

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

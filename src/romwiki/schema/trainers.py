from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from typing import Any, Literal, NotRequired, TypedDict

from romwiki.schema.pokemon import RecordProvenance
from romwiki.util.errors import DataSourceError

TrainerBattleConditionKind = Literal[
    "starter-choice",
    "difficulty-mode",
    "rematch-stage",
    "story-stage",
    "sibling-version",
    "season",
]
TrainerVariantSupportStatus = Literal[
    "verified", "partial", "unsupported", "unresolved"
]


class TrainerBattleCondition(TypedDict):
    """One independently selectable axis for an exact trainer record."""

    kind: TrainerBattleConditionKind
    value: str
    label: str


class TrainerBattleVariant(TypedDict):
    """A conditioned reference to an exact trainer record."""

    trainer_id: int
    order: int
    conditions: list[TrainerBattleCondition]


class TrainerBattleRuleProvenance(TypedDict):
    """Evidence for the selection rule relating a family of records."""

    source: str
    reference: str
    verification: str


class TrainerBattleFamily(TypedDict):
    """A verified relationship over exact trainer records."""

    id: str
    label: str
    order: int
    provenance: TrainerBattleRuleProvenance
    variants: list[TrainerBattleVariant]


class TrainerVariantMechanicSupport(TypedDict, total=False):
    status: TrainerVariantSupportStatus
    note: str
    runtime: dict[str, Any]


class TrainerVariantSupport(TypedDict):
    """Per-profile coverage; absence never implies that a mechanic was decoded."""

    starter_choice: TrainerVariantMechanicSupport
    difficulty_mode: TrainerVariantMechanicSupport
    rematch_stage: TrainerVariantMechanicSupport
    story_stage: TrainerVariantMechanicSupport
    sibling_version: TrainerVariantMechanicSupport
    season: TrainerVariantMechanicSupport


_CONDITION_KINDS = {
    "starter-choice",
    "difficulty-mode",
    "rematch-stage",
    "story-stage",
    "sibling-version",
    "season",
}
_SUPPORT_KEYS = {
    "starter_choice",
    "difficulty_mode",
    "rematch_stage",
    "story_stage",
    "sibling_version",
    "season",
}
_SUPPORT_STATUSES = {"verified", "partial", "unsupported", "unresolved"}


def unresolved_trainer_variant_support() -> TrainerVariantSupport:
    """Conservative fallback for inputs whose variant mechanics are unverified."""
    return {
        "starter_choice": {"status": "unresolved"},
        "difficulty_mode": {"status": "unresolved"},
        "rematch_stage": {"status": "unresolved"},
        "story_stage": {"status": "unresolved"},
        "sibling_version": {"status": "unresolved"},
        "season": {"status": "unresolved"},
    }


def unverified_trainer_variants() -> dict[str, Any]:
    """Trainer variants for a build no variant contract has been verified against.

    Every mechanic is unresolved and no battle families are published, so a
    new hack's trainers can be built from its profile alone without applying
    selectors that were only verified against other builds.
    """
    return {
        "trainer_variant_support": unresolved_trainer_variant_support(),
        "battle_families": [],
    }


def validate_trainer_battle_families(
    families: object,
    support: object,
    trainer_ids: Iterable[int],
) -> None:
    """Validate the shared relationship contract at pipeline boundaries."""
    if not isinstance(families, list):
        raise DataSourceError("Trainer battle families must be a list")
    if not isinstance(support, Mapping) or set(support) != _SUPPORT_KEYS:
        raise DataSourceError("Trainer variant support must declare every mechanic")
    for mechanic, declaration in support.items():
        if (
            not isinstance(declaration, Mapping)
            or declaration.get("status") not in _SUPPORT_STATUSES
        ):
            raise DataSourceError(
                f"Trainer variant support for {mechanic!r} is invalid"
            )

    available_ids = set(trainer_ids)
    family_ids: set[str] = set()
    family_orders: set[int] = set()
    for family in families:
        if not isinstance(family, Mapping):
            raise DataSourceError("Trainer battle family entries must be objects")
        family_id = family.get("id")
        label = family.get("label")
        order = family.get("order")
        provenance = family.get("provenance")
        variants = family.get("variants")
        if not isinstance(family_id, str) or not family_id or family_id in family_ids:
            raise DataSourceError(
                f"Duplicate or invalid trainer battle family ID: {family_id!r}"
            )
        if not isinstance(label, str) or not label:
            raise DataSourceError(f"Trainer battle family {family_id!r} has no label")
        if not isinstance(order, int) or order < 0 or order in family_orders:
            raise DataSourceError(
                f"Trainer battle family {family_id!r} has invalid order"
            )
        if not isinstance(provenance, Mapping) or any(
            not isinstance(provenance.get(field), str) or not provenance[field]
            for field in ("source", "reference", "verification")
        ):
            raise DataSourceError(
                f"Trainer battle family {family_id!r} lacks rule provenance"
            )
        if not isinstance(variants, list) or len(variants) < 2:
            raise DataSourceError(
                f"Trainer battle family {family_id!r} needs at least two variants"
            )

        seen_variants: set[tuple[int, tuple[tuple[str, str], ...]]] = set()
        variant_orders: set[int] = set()
        for variant in variants:
            if not isinstance(variant, Mapping):
                raise DataSourceError(
                    f"Trainer battle family {family_id!r} has an invalid variant"
                )
            trainer_id = variant.get("trainer_id")
            variant_order = variant.get("order")
            conditions = variant.get("conditions")
            if not isinstance(trainer_id, int) or trainer_id not in available_ids:
                raise DataSourceError(
                    f"Trainer battle family {family_id!r} references missing trainer {trainer_id!r}"
                )
            if (
                not isinstance(variant_order, int)
                or variant_order < 0
                or variant_order in variant_orders
            ):
                raise DataSourceError(
                    f"Trainer battle family {family_id!r} has duplicate variant order"
                )
            identity = (
                trainer_id,
                _normalize_trainer_variant_conditions(family_id, conditions),
            )
            if identity in seen_variants:
                raise DataSourceError(
                    f"Trainer battle family {family_id!r} has a duplicate variant"
                )
            seen_variants.add(identity)
            variant_orders.add(variant_order)
        family_ids.add(family_id)
        family_orders.add(order)


def _normalize_trainer_variant_conditions(
    family_id: str, conditions: object
) -> tuple[tuple[str, str], ...]:
    if not isinstance(conditions, list) or not conditions:
        raise DataSourceError(
            f"Trainer battle family {family_id!r} has an unconditioned variant"
        )
    normalized: list[tuple[str, str]] = []
    condition_kinds: set[str] = set()
    for condition in conditions:
        if not isinstance(condition, Mapping):
            raise DataSourceError(
                f"Trainer battle family {family_id!r} has an invalid condition"
            )
        kind = condition.get("kind")
        value = condition.get("value")
        label = condition.get("label")
        if kind not in _CONDITION_KINDS or kind in condition_kinds:
            raise DataSourceError(
                f"Trainer battle family {family_id!r} has contradictory condition {kind!r}"
            )
        if (
            not isinstance(value, str)
            or not value
            or not isinstance(label, str)
            or not label
        ):
            raise DataSourceError(
                f"Trainer battle family {family_id!r} has an invalid condition value"
            )
        condition_kinds.add(kind)
        normalized.append((kind, value))
    return tuple(sorted(normalized))


class TrainerAttribute(TypedDict):
    """A stored or derived party attribute with explicit provenance.

    `slot`/`name`/`values`/`limitation` are each populated by only some
    attribute kinds (e.g. `ability` carries `slot`, `nature`/`gender` carry
    `name`, `ivs`/`evs`/`calculated_stats` carry `values`).
    """

    source: Literal["stored", "derived", "engine-default"]
    slot: NotRequired[int]
    name: NotRequired[str]
    values: NotRequired[dict[str, Any]]
    limitation: NotRequired[str]


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
    iv_strength: int
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
    # None marks a field the engine has not decoded, as opposed to a stored
    # zero or blank value.
    class_name: str | None
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
    healer: bool | None
    victory_money_multiplier: int | None
    victory_item_id: int | None
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


# Some ROMs (confirmed in Black 2/White 2 and its hacks) reserve trainer IDs
# that were never assigned a class, so the class-name text bank falls back to
# this literal placeholder. Real trainers can have a blank display name (e.g.
# rank-and-file grunts identified only by class), so blank name alone isn't a
# safe signal -- the placeholder class name is what actually marks a record
# as an unused stub.
UNUSED_TRAINER_CLASS_NAME = "no data"


def is_unused_trainer_slot(record: Mapping[str, Any]) -> bool:
    """Report whether a trainer record is a reserved-but-never-filled-in slot."""

    class_name = record["class_name"]
    return (
        class_name is not None
        and class_name.strip().lower() == UNUSED_TRAINER_CLASS_NAME
    )

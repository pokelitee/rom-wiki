from __future__ import annotations

from typing import Any, Literal, NotRequired, Required, TypedDict

from romwiki.schema.trainers import TrainerBattleFamily, TrainerVariantSupport

# Semantic shapes declared by an engine adapter. Encounter and location
# envelopes publish theirs so consumers never resolve the engine to dispatch.
EncounterFormat = Literal["unsupported", "conditional", "seasonal", "method-table"]
LocationFormat = Literal["unsupported", "event-map", "encounter-map"]


class EnrichedReference(TypedDict, total=False):
    source: str
    source_url: str
    name: str
    short_effect: str
    effect: str
    flavor_text: str
    flavor_text_label: str
    flavor_text_source: str
    version: str
    metadata: dict[str, Any]


class VersionedEnrichedRecord(TypedDict, total=False):
    """Fields a sibling-version merge adds to any enriched record."""

    versions: list[str]
    version_variants: dict[str, dict[str, Any]]
    reference_variants: dict[str, EnrichedReference | None]


class NamedId(TypedDict):
    id: int
    name: str


class EntityLink(TypedDict):
    """A cross-reference to an ability or item; ID 0 means "none"."""

    id: int
    slug: str | None
    name: str | None


class MoveLink(TypedDict):
    id: int
    slug: str
    name: str


class PokemonMemberLink(TypedDict):
    member: int
    national_dex_id: int
    slug: str
    name: str


class PokemonHeldItem(EntityLink):
    rarity: str


class PokemonAbilitySlot(EntityLink):
    is_hidden: bool


class MachineCompatibility(TypedDict):
    id: int
    name: str
    # Absent when the engine exposes no machine dataset: only the stored
    # compatibility bit and its generated machine name are known.
    kind: NotRequired[str]
    number: NotRequired[int]
    item_id: NotRequired[int | None]
    move: NotRequired[MoveLink]


class TutorLocation(TypedDict):
    id: int | None
    name: str


class TutorRecord(TypedDict, total=False):
    """A raw tutor record plus its resolved location."""

    tutor_id: Required[int]
    move_id: Required[int]
    location: Required[TutorLocation]
    kind: str
    location_id: int
    location_name: str
    table_index: int
    shard_costs: dict[str, int]
    battle_point_cost: int
    eligibility_kind: str
    eligibility_value: int | list[int]
    minimum_friendship: int
    script_member: int
    command_offset: int
    map_header_id: int


class TutorMoveCompatibility(TutorRecord, total=False):
    move: Required[MoveLink]


class LevelUpMove(TypedDict):
    level: int
    move: MoveLink


class EvolutionParameter(TypedDict, total=False):
    kind: Required[str]
    id: int
    slug: str | None
    name: str | None
    value: int


class EvolutionTarget(TypedDict):
    id: int
    slug: str
    name: str


class PokemonEvolution(TypedDict):
    method_id: int
    parameter: int
    target_species_id: int
    method: NamedId
    parameter_data: EvolutionParameter | None
    target: EvolutionTarget


class PokemonStaticEncounter(TypedDict):
    level: int
    is_egg: bool


class PokemonBattleForm(TypedDict):
    label: str
    base_stats: dict[str, int]
    types: list[NamedId]


class PokemonIdentityFields(TypedDict):
    member: int
    slug: str
    name: str
    public: bool
    national_dex_id: int | None
    base_species: str | None
    form: str | None
    sprite: dict[str, Any] | None
    portrait: dict[str, Any] | None
    cry: dict[str, Any] | None
    sprites: list[dict[str, Any]]
    reference: dict[str, Any] | None


class PokemonSpeciesTraits(TypedDict):
    base_stats: dict[str, int]
    types: list[NamedId]
    catch_rate: int
    base_experience: int
    ev_yields: dict[str, int]
    held_items: list[PokemonHeldItem]
    gender_ratio: int
    hatch_cycles: int
    base_friendship: int
    growth_rate: NamedId | None
    egg_groups: list[NamedId]
    abilities: list[PokemonAbilitySlot]
    safari_flee_rate: int
    body_color: NamedId | None
    flip_sprite: bool


class PokemonMoveCompatibility(TypedDict):
    machines: list[MachineCompatibility]
    tutor_moves: list[TutorMoveCompatibility]


class PokemonLearnsetFields(TypedDict):
    level_up_moves: list[LevelUpMove]
    learnset_provenance: dict[str, Any] | None
    egg_moves: list[MoveLink]
    egg_move_provenance: dict[str, Any] | None


class PokemonEvolutionFields(TypedDict):
    evolutions: list[PokemonEvolution]
    evolution_provenance: dict[str, Any] | None


class PokemonEnrichedRecord(
    VersionedEnrichedRecord,
    PokemonIdentityFields,
    PokemonSpeciesTraits,
    PokemonMoveCompatibility,
    PokemonLearnsetFields,
    PokemonEvolutionFields,
):
    static_encounters: list[PokemonStaticEncounter]
    provenance: dict[str, Any]
    battle_forms: NotRequired[list[PokemonBattleForm]]


class ReplacedMove(TypedDict):
    slug: str
    name: str


class MoveTutor(TutorRecord, total=False):
    compatible_pokemon: Required[list[PokemonMemberLink]]


class MoveFields(TypedDict):
    """The shared raw `Move` contract, carried through enrichment unchanged."""

    move_id: int
    effect_id: int
    damage_class_id: int
    power: int
    type_id: int
    accuracy: int
    pp: int
    effect_chance: int
    target_id: int
    priority: int
    flags: int
    provenance: dict[str, Any]
    contest_effect_id: NotRequired[int]
    contest_type_id: NotRequired[int]


class MoveEnrichedFields(TypedDict):
    slug: str
    name: str
    replaces: ReplacedMove | None
    reference: dict[str, Any] | None
    public: bool
    damage_class: NamedId
    type: NamedId
    machines: list[dict[str, Any]]
    tutors: list[MoveTutor]
    egg_move_pokemon: list[PokemonMemberLink]


class MoveEnrichedRecord(VersionedEnrichedRecord, MoveFields, MoveEnrichedFields):
    pass


class AbilityPokemon(TypedDict):
    member: int
    national_dex_id: int | None
    slug: str
    name: str
    sprite: dict[str, Any] | None
    slots: list[int]
    is_hidden: bool


class AbilityEnrichedRecord(VersionedEnrichedRecord):
    ability_id: int
    slug: str | None
    name: str
    reference: dict[str, Any] | None
    pokemon: list[AbilityPokemon]
    pickup: dict[str, Any] | None


class ItemEnrichedFields(TypedDict):
    slug: str
    reference: dict[str, Any] | None
    wild_held_by: list[dict[str, Any]]
    trainer_held_by: list[dict[str, Any]]
    trainer_battle_items: list[dict[str, Any]]
    trainer_rewards: list[dict[str, Any]]
    locations: list[dict[str, Any]]
    shops: list[dict[str, Any]]
    gifts: list[dict[str, Any]]
    trades: list[dict[str, Any]]
    evolutions: list[dict[str, Any]]
    revives_into: dict[str, Any] | None
    revives_at: list[dict[str, Any]]


class ItemEnrichedRecord(VersionedEnrichedRecord, ItemEnrichedFields, total=False):
    """A raw item record plus its reference data and reverse relationships.

    Raw mechanic fields vary by engine and are left untyped here.
    """

    item_id: Required[int]
    name: Required[str]
    public: Required[bool]
    provenance: Required[dict[str, Any]]
    revives_into_species_id: int | None


class TrainerItem(EntityLink):
    sprite_url: str | None


class TrainerEnrichedFields(TypedDict):
    party: list[dict[str, Any]]
    base_prize_money: dict[str, Any] | None
    victory_item: TrainerItem | None
    ai_battle_items: list[TrainerItem]


class TrainerEnrichedRecord(
    VersionedEnrichedRecord, TrainerEnrichedFields, total=False
):
    """A raw trainer record plus its resolved party, items, and prize money.

    Raw storage fields vary by trainer format and are left untyped here.
    """

    trainer_id: Required[int]
    name: Required[str]
    class_id: Required[int]
    class_name: Required[str | None]
    provenance: Required[dict[str, Any]]
    locations: Required[list[dict[str, Any]]]


class EncounterPokemon(TypedDict):
    # The engine-native species identifier, not the National Dex number.
    id: int
    slug: str
    name: str
    sprite: dict[str, Any] | None


class EncounterSlot(TypedDict, total=False):
    """A raw encounter slot plus its odds and resolved Pokémon."""

    species_id: Required[int]
    chance: Required[int]
    pokemon: Required[EncounterPokemon | None]
    level: int
    minimum_level: int
    maximum_level: int
    form_id: int


class EncounterMethodTable(TypedDict):
    rate: int
    slots: list[EncounterSlot]


class ReplacementSlot(TypedDict):
    """A special-condition species replacing one walking slot."""

    pokemon: EncounterPokemon | None
    level: int
    chance: int


class SlottedSpecialEncounters(TypedDict):
    swarm: list[ReplacementSlot]
    day: list[ReplacementSlot]
    night: list[ReplacementSlot]
    radar: list[EncounterPokemon | None]
    unown_forms: list[str]
    dual_slot: dict[str, list[ReplacementSlot]]


class DirectSpecialEncounters(TypedDict):
    """Special-condition species named directly rather than as slot swaps."""

    format: Literal["direct-species"]
    land_swarm: EncounterPokemon | None
    surf_swarm: EncounterPokemon | None
    hoenn_radio: list[EncounterPokemon | None]
    sinnoh_radio: list[EncounterPokemon | None]
    night_fishing: EncounterPokemon | None
    fishing_swarm: EncounterPokemon | None


class EncounterEnrichedRecord(VersionedEnrichedRecord, total=False):
    """One wild-encounter area or conditional encounter source.

    Area shapes differ by the dataset's encounter format, and conditional
    sources (`source_type`) keep their raw fields, so only the fields every
    record carries are required.
    """

    area_id: Required[int]
    name: Required[str]
    active: Required[bool]
    provenance: dict[str, Any]
    locations: list[dict[str, Any]]
    walking: EncounterMethodTable
    walking_variants: dict[str, EncounterMethodTable]
    surf: EncounterMethodTable
    rock_smash: EncounterMethodTable
    old_rod: EncounterMethodTable
    good_rod: EncounterMethodTable
    super_rod: EncounterMethodTable
    special: SlottedSpecialEncounters | DirectSpecialEncounters
    bonus_slot_methodology_source: str
    encounter_form_rates: list[int]
    unown_table_id: int
    map_index: int
    season: str | None
    slug: int | str
    location_names: list[str]
    land: EncounterMethodTable
    water: EncounterMethodTable
    fishing: EncounterMethodTable
    source_type: str
    location: dict[str, Any]
    pokemon: Any
    pools: dict[str, list[dict[str, Any]]]
    methods: dict[str, dict[str, Any]]
    area_name: str
    visible_items: list[dict[str, Any]]
    hidden_items: list[dict[str, Any]]


class LocationEnrichedRecord(VersionedEnrichedRecord, total=False):
    """A normalized location; its shape depends on the location format."""

    header_id: Required[int]
    name: Required[str]
    provenance: dict[str, Any]
    section_name: str | None


class EnrichedDataset[RecordT: VersionedEnrichedRecord](TypedDict, total=False):
    schema_version: Required[int]
    game: Required[str]
    engine: Required[str]
    dataset: Required[str]
    record_count: Required[int]
    source: Required[dict[str, Any]]
    records: Required[list[RecordT]]
    # Attached after enrichment from the exact engine/profile combination.
    features: list[str]
    name_source: dict[str, Any] | None
    description_source: dict[str, Any] | None
    name_sources: dict[str, Any]
    description_sources: dict[str, dict[str, Any]]
    supplemental_sources: dict[str, dict[str, Any] | None]


class PokemonDataset(EnrichedDataset[PokemonEnrichedRecord], total=False):
    public_record_count: Required[int]
    ability_names: list[str]
    ability_descriptions: list[str]


class MoveDataset(EnrichedDataset[MoveEnrichedRecord], total=False):
    public_record_count: Required[int]


class AbilityDataset(EnrichedDataset[AbilityEnrichedRecord], total=False):
    assigned_record_count: Required[int]


class ItemDataset(EnrichedDataset[ItemEnrichedRecord], total=False):
    referenced_record_count: Required[int]


class TrainerDataset(EnrichedDataset[TrainerEnrichedRecord], total=False):
    party_schema_version: Required[int]
    battle_family_schema_version: Required[int]
    trainer_variant_support: Required[TrainerVariantSupport]
    battle_families: Required[list[TrainerBattleFamily]]
    active_record_count: Required[int]
    linked_record_count: Required[int]
    location_reference_count: Required[int]


class EncounterDataset(EnrichedDataset[EncounterEnrichedRecord], total=False):
    encounter_format: Required[EncounterFormat]
    active_record_count: Required[int]


class LocationDataset(EnrichedDataset[LocationEnrichedRecord], total=False):
    location_format: Required[LocationFormat]

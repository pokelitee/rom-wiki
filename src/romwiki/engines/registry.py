from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from types import ModuleType
from typing import Any, Literal, get_args

import romwiki.engines.gen3.emerald as gen3_emerald
import romwiki.engines.gen3.frlg as gen3_frlg
import romwiki.engines.gen4.hgss as gen4_hgss
import romwiki.engines.gen4.platinum as gen4_platinum
import romwiki.engines.gen5.b2w2 as gen5_b2w2
import romwiki.engines.gen5.bw as gen5_bw
from romwiki.engines.concerns import (
    EggMoveConcern,
    EncounterConcern,
    EnrichmentTables,
    EvolutionConcern,
    ItemConcern,
    LearnsetConcern,
    LocationConcern,
    MachineConcern,
    MartConcern,
    MoveConcern,
    PersonalConcern,
    PickupConcern,
    ReferenceNameConcern,
    StaticEncounterConcern,
    TradeConcern,
    TrainerConcern,
    TrainerPartyConcern,
    TutorConcern,
)
from romwiki.engines.profile_contracts import (
    GEN3_EMERALD_PROFILE_CONTRACT,
    GEN3_FRLG_PROFILE_CONTRACT,
    GEN4_HGSS_PROFILE_CONTRACT,
    GEN4_PLATINUM_PROFILE_CONTRACT,
    GEN5_B2W2_PROFILE_CONTRACT,
    GEN5_BW_PROFILE_CONTRACT,
    EngineProfileContract,
)
from romwiki.schema.enriched import EncounterFormat, LocationFormat
from romwiki.util.errors import DataSourceError

# Canonical engine identifiers used by registration and contract tests.
GEN3_FRLG_ENGINE = "gen3_frlg"
GEN3_EMERALD_ENGINE = "gen3_emerald"
GEN4_PLATINUM_ENGINE = "gen4_platinum"
GEN4_HGSS_ENGINE = "gen4_hgss"
GEN5_BW_ENGINE = "gen5_bw"
GEN5_B2W2_ENGINE = "gen5_b2w2"

LocationExtractionFormat = Literal[
    "unsupported",
    "arm9-event-map",
    "arm9-encounter-map",
    "archive-encounter-map",
    "gba-map-groups",
]
PickupFormat = Literal["none", "locator-tables", "split-table", "sliding-table"]
TrainerFormat = Literal["unsupported", "class-gender", "battle-mode", "pointer-party"]
TutorFormat = Literal[
    "none", "overlay-table", "overlay-archive", "personal-archive", "flat-offset-table"
]
FossilFormat = Literal["none", "arm9-table", "script-pattern"]
StaticEncounterFormat = Literal["none", "script-commands"]
EggMoveFormat = Literal[
    "none", "overlay-table", "archive-table", "species-archive", "flat-offset-table"
]
ItemArchiveFormat = Literal["archive-index", "arm9-map"]
MachineFormat = Literal["none", "profile-offset", "binary-prefix"]

# Optional engine features that shared pipeline code checks for by name. An
# adapter declares the ones it supports in `capabilities`; registration
# rejects unknown names and verifies each declared feature's members.
DETACHED_NPC_TRADES = "detached-npc-trades"
COMPRESSED_CODE_BINARY = "compressed-code-binary"
TRAINER_LOCATIONS = "trainer-locations"
TRAINER_SCRIPT_REFERENCES = "trainer-script-references"
TAG_BATTLES = "tag-battles"
REMATCH_TABLE = "rematch-table"
DIFFICULTY_BRANCHES = "difficulty-branches"
LOCATION_SPECIAL_VENDORS = "location-special-vendors"

DATASET_KINDS = (
    "pokemon",
    "abilities",
    "moves",
    "items",
    "encounters",
    "trainers",
    "locations",
)
DEFAULT_REQUIRED_DATASET_KINDS = frozenset({"pokemon", "moves", "items", "encounters"})
_DATASET_DEPENDENCIES = {
    "abilities": frozenset({"pokemon"}),
    "items": frozenset({"pokemon"}),
    "trainers": frozenset({"pokemon", "moves"}),
    "locations": frozenset({"items"}),
}


@dataclass(frozen=True, slots=True)
class EngineFormats:
    encounters: EncounterFormat
    locations: LocationFormat
    location_extraction: LocationExtractionFormat
    pickup: PickupFormat
    trainers: TrainerFormat
    tutors: TutorFormat
    fossils: FossilFormat
    static_encounters: StaticEncounterFormat
    egg_moves: EggMoveFormat
    item_archive: ItemArchiveFormat
    machines: MachineFormat


@dataclass(frozen=True, slots=True)
class EngineAdapter:
    """Namespace of everything the pipeline needs from one engine implementation.

    Each concern field is the namespace providing that concern's parsers,
    constants, and record types, typed by the members the pipeline reads. A
    pipeline module looks up the adapter for the current profile's engine and
    accesses names through it instead of importing a specific engine package
    directly.
    """

    personal: PersonalConcern
    locations: LocationConcern
    trainers: TrainerConcern
    encounters: EncounterConcern
    evolutions: EvolutionConcern
    items: ItemConcern
    machines: MachineConcern
    moves: MoveConcern
    tutors: TutorConcern
    egg_moves: EggMoveConcern
    learnsets: LearnsetConcern
    reference_names: ReferenceNameConcern
    enrich: EnrichmentTables
    trainer_party: TrainerPartyConcern
    trades: TradeConcern
    marts: MartConcern
    static_encounters: StaticEncounterConcern
    pickup: PickupConcern
    formats: EngineFormats
    generation: int | None = None
    presentation_features: frozenset[str] = frozenset()
    capabilities: frozenset[str] = frozenset()
    dataset_kinds: frozenset[str] = frozenset(DATASET_KINDS)
    required_dataset_kinds: frozenset[str] = DEFAULT_REQUIRED_DATASET_KINDS
    profile_contract: EngineProfileContract = EngineProfileContract()


_CONCERN_FIELDS = (
    "personal",
    "locations",
    "trainers",
    "encounters",
    "evolutions",
    "items",
    "machines",
    "moves",
    "tutors",
    "egg_moves",
    "learnsets",
    "reference_names",
    "enrich",
    "trainer_party",
    "trades",
    "marts",
    "static_encounters",
    "pickup",
)


def single_namespace_adapter(
    namespace: ModuleType,
    *,
    formats: EngineFormats,
    generation: int | None = None,
    presentation_features: frozenset[str] = frozenset(),
    capabilities: frozenset[str] = frozenset(),
    dataset_kinds: frozenset[str] = frozenset(DATASET_KINDS),
    required_dataset_kinds: frozenset[str] = DEFAULT_REQUIRED_DATASET_KINDS,
    profile_contract: EngineProfileContract,
) -> EngineAdapter:
    """Build an adapter whose every concern is one engine package's namespace."""
    # A package provides only the members its declared formats, datasets, and
    # capabilities need, so it cannot statically satisfy every concern
    # protocol; `_validate_engine_adapter` checks those members instead.
    concerns: Any = namespace
    return EngineAdapter(
        **dict.fromkeys(_CONCERN_FIELDS, concerns),
        formats=formats,
        generation=generation,
        presentation_features=presentation_features,
        capabilities=capabilities,
        dataset_kinds=dataset_kinds,
        required_dataset_kinds=required_dataset_kinds,
        profile_contract=profile_contract,
    )


_ENGINES: dict[str, EngineAdapter] = {
    GEN3_FRLG_ENGINE: single_namespace_adapter(
        # Concerns Generation III lacks (pickup, fossils, static encounters)
        # are never accessed because `formats` declares them "none"
        # (enforced by `_validate_engine_adapter`).
        gen3_frlg,
        formats=EngineFormats(
            encounters="method-table",
            locations="encounter-map",
            location_extraction="gba-map-groups",
            pickup="none",
            trainers="pointer-party",
            tutors="flat-offset-table",
            fossils="none",
            static_encounters="none",
            egg_moves="flat-offset-table",
            item_archive="archive-index",
            machines="profile-offset",
        ),
        generation=3,
        dataset_kinds=frozenset(
            {
                "pokemon",
                "moves",
                "items",
                "trainers",
                "abilities",
                "encounters",
                "locations",
            }
        ),
        required_dataset_kinds=frozenset({"pokemon"}),
        profile_contract=GEN3_FRLG_PROFILE_CONTRACT,
    ),
    GEN3_EMERALD_ENGINE: single_namespace_adapter(
        # The `gen3_emerald` namespace re-exports FireRed/LeafGreen-proven-identical
        # parsers from `gen3/shared/` (see that package's module comments
        # for the real-ROM cross-checks proving each shared fact).
        gen3_emerald,
        formats=EngineFormats(
            encounters="method-table",
            locations="encounter-map",
            location_extraction="gba-map-groups",
            pickup="none",
            trainers="pointer-party",
            tutors="flat-offset-table",
            fossils="none",
            static_encounters="none",
            egg_moves="flat-offset-table",
            item_archive="archive-index",
            machines="profile-offset",
        ),
        generation=3,
        dataset_kinds=frozenset(
            {
                "pokemon",
                "abilities",
                "moves",
                "items",
                "trainers",
                "encounters",
                "locations",
            }
        ),
        required_dataset_kinds=frozenset({"pokemon"}),
        profile_contract=GEN3_EMERALD_PROFILE_CONTRACT,
    ),
    GEN4_PLATINUM_ENGINE: single_namespace_adapter(
        gen4_platinum,
        formats=EngineFormats(
            encounters="conditional",
            locations="event-map",
            location_extraction="arm9-event-map",
            pickup="split-table",
            trainers="class-gender",
            tutors="overlay-table",
            fossils="arm9-table",
            static_encounters="none",
            egg_moves="overlay-table",
            item_archive="arm9-map",
            machines="profile-offset",
        ),
        generation=4,
        presentation_features=frozenset({"contests"}),
        capabilities=frozenset(
            {TRAINER_LOCATIONS, TRAINER_SCRIPT_REFERENCES, TAG_BATTLES, REMATCH_TABLE}
        ),
        profile_contract=GEN4_PLATINUM_PROFILE_CONTRACT,
    ),
    GEN4_HGSS_ENGINE: single_namespace_adapter(
        gen4_hgss,
        formats=EngineFormats(
            encounters="conditional",
            locations="encounter-map",
            location_extraction="arm9-encounter-map",
            pickup="locator-tables",
            trainers="class-gender",
            tutors="overlay-archive",
            fossils="none",
            static_encounters="none",
            egg_moves="archive-table",
            item_archive="arm9-map",
            machines="binary-prefix",
        ),
        generation=4,
        dataset_kinds=frozenset(
            {
                "pokemon",
                "abilities",
                "moves",
                "items",
                "encounters",
                "trainers",
                "locations",
            }
        ),
        required_dataset_kinds=frozenset({"pokemon"}),
        capabilities=frozenset(
            {
                DETACHED_NPC_TRADES,
                COMPRESSED_CODE_BINARY,
                TRAINER_LOCATIONS,
                TRAINER_SCRIPT_REFERENCES,
            }
        ),
        profile_contract=GEN4_HGSS_PROFILE_CONTRACT,
    ),
    GEN5_BW_ENGINE: single_namespace_adapter(
        gen5_bw,
        formats=EngineFormats(
            encounters="seasonal",
            locations="encounter-map",
            location_extraction="archive-encounter-map",
            pickup="sliding-table",
            trainers="battle-mode",
            tutors="none",
            fossils="script-pattern",
            static_encounters="script-commands",
            egg_moves="species-archive",
            item_archive="archive-index",
            machines="binary-prefix",
        ),
        generation=5,
        presentation_features=frozenset(
            {
                "post-battle-healing",
                "victory-items",
            }
        ),
        capabilities=frozenset({DETACHED_NPC_TRADES}),
        profile_contract=GEN5_BW_PROFILE_CONTRACT,
    ),
    GEN5_B2W2_ENGINE: single_namespace_adapter(
        gen5_b2w2,
        formats=EngineFormats(
            encounters="seasonal",
            locations="encounter-map",
            location_extraction="archive-encounter-map",
            pickup="sliding-table",
            trainers="battle-mode",
            tutors="personal-archive",
            fossils="script-pattern",
            static_encounters="script-commands",
            egg_moves="species-archive",
            item_archive="archive-index",
            machines="binary-prefix",
        ),
        generation=5,
        presentation_features=frozenset(
            {
                "post-battle-healing",
                "victory-items",
            }
        ),
        capabilities=frozenset(
            {DETACHED_NPC_TRADES, DIFFICULTY_BRANCHES, LOCATION_SPECIAL_VENDORS}
        ),
        profile_contract=GEN5_B2W2_PROFILE_CONTRACT,
    ),
}


_FORMAT_TYPES = {
    "encounters": EncounterFormat,
    "locations": LocationFormat,
    "location_extraction": LocationExtractionFormat,
    "pickup": PickupFormat,
    "trainers": TrainerFormat,
    "tutors": TutorFormat,
    "fossils": FossilFormat,
    "static_encounters": StaticEncounterFormat,
    "egg_moves": EggMoveFormat,
    "item_archive": ItemArchiveFormat,
    "machines": MachineFormat,
}
_LOCATION_EXTRACTION_SHAPES = {
    "unsupported": "unsupported",
    "arm9-event-map": "event-map",
    "arm9-encounter-map": "encounter-map",
    "archive-encounter-map": "encounter-map",
    "gba-map-groups": "encounter-map",
}
_STARTER_SELECTION_MEMBERS = (
    "parse_starter_branch_families",
    "parse_starter_species",
    "STARTER_SPECIES_ENTRY_SIZE",
    "BASE_SPECIES_COUNT",
)
_EVENT_MAP_ITEM_MEMBERS = (
    "find_script_awarded_items",
    "is_hidden_item_candidate",
    "is_visible_item_candidate",
)
# Members each supported dataset reads, keyed by concern.
_DATASET_REQUIRED_MEMBERS: dict[str, dict[str, tuple[str, ...]]] = {
    "pokemon": {
        "personal": (
            "parse_personal_record",
            "PERSONAL_RECORD_COUNT",
            "PERSONAL_RECORD_SIZE",
        ),
        "enrich": (
            "ABILITY_REFERENCE_IDS",
            "ALLOW_DUPLICATE_EGG_MOVES",
            "INTERNAL_TO_NATIONAL_DEX",
            "POKEMON_DESCRIPTION_COUNT",
            "TRANSFORMATION_MEMBERS",
        ),
    },
    "moves": {"moves": ("parse_move_record",)},
    "items": {"items": ("parse_item_record",)},
    "encounters": {
        "enrich": ("ENCOUNTER_COSMETIC_FORM_LABELS", "ENCOUNTER_FORM_SLUGS"),
    },
    "trainers": {"trainer_party": ("normalize_trainer_party_member",)},
}
# Members each declared format reads, keyed by (format field, format) and then
# by concern.
_FORMAT_REQUIRED_MEMBERS: dict[tuple[str, str], dict[str, tuple[str, ...]]] = {
    ("encounters", "conditional"): {"encounters": ("parse_encounter_record",)},
    ("encounters", "seasonal"): {"encounters": ("parse_encounter_entry",)},
    ("encounters", "method-table"): {"encounters": ("parse_encounter_record",)},
    ("locations", "event-map"): {"locations": ("parse_map_headers",)},
    ("locations", "encounter-map"): {"locations": ("parse_map_header_table",)},
    ("location_extraction", "arm9-event-map"): {
        "locations": (
            *_EVENT_MAP_ITEM_MEMBERS,
            "GAME_CORNER_PRIZE_EXCHANGE_HEADER_ID",
            "GREAT_MARSH_HEADER_IDS",
            "GREAT_MARSH_POST_NATIONAL_DEX_MEMBER",
            "GREAT_MARSH_PRE_NATIONAL_DEX_MEMBER",
            "HONEY_TREE_COMMON_MEMBER",
            "HONEY_TREE_HEADER_IDS",
            "HONEY_TREE_RARE_MEMBER",
            "HONEY_TREE_UNCOMMON_MEMBER",
            "TROPHY_GARDEN_HEADER_ID",
            "TROPHY_GARDEN_MEMBER",
        )
    },
    ("location_extraction", "arm9-encounter-map"): {
        "locations": (
            *_EVENT_MAP_ITEM_MEMBERS,
            "ITEM_BALL_TABLE_SCRIPT_MEMBER",
            "parse_egg_gift_commands",
            "parse_hidden_item_table",
            "parse_item_ball_table",
            "parse_mart_dispatch_commands",
            "parse_pokemon_gift_commands",
            "parse_static_encounter_commands",
            "parse_togepi_egg_gift_commands",
        )
    },
    ("location_extraction", "archive-encounter-map"): {
        "locations": (
            "NPC_TRADE_TEXT_MEMBER_BY_ID",
            "WARP_DESTINATION_INDEXED",
            "is_visible_item_candidate",
        )
    },
    ("location_extraction", "gba-map-groups"): {
        "locations": (
            "FIRST_REGION_MAP_SECTION",
            "GMAPGROUPS_GROUP_COUNT",
            "REGION_NAME_ENTRY_SIZE",
            "REGION_NAME_POINTER_OFFSET",
            "parse_gmapgroups_pointers",
            "parse_map_group_index",
            "BG_EVENT_HIDDEN_ITEM",
            "BG_EVENT_SCRIPT_KINDS",
            "BG_EVENT_SIZE",
            "COORD_EVENT_SIZE",
            "DYNAMIC_MAP",
            "EVENT_MON_SPECIAL",
            "GBA_MAP_EVENTS_SIZE",
            "INGAME_TRADE_SIZE",
            "NATURE_NAMES",
            "MAP_CONNECTIONS_SIZE",
            "MAP_CONNECTION_SIZE",
            "OBJECT_EVENT_TEMPLATE_SIZE",
            "SCRIPT_COMMANDS",
            "SCRIPT_WARP_COMMANDS",
            "TRADE_INFO_SPECIAL",
            "WARP_EVENT_SIZE",
            "decode_gen3_name_table",
            "decode_hidden_item",
            "disassemble_script",
            "find_given_items",
            "find_item_ball",
            "find_marts",
            "find_pokemon",
            "find_trades",
            "parse_bg_event",
            "parse_coord_event_script",
            "parse_gba_map_events",
            "parse_ingame_trade",
            "parse_map_connection",
            "parse_map_connections",
            "parse_warp_event",
            "parse_object_event_template",
            "resolve_gba_pointer",
        )
    },
    ("pickup", "split-table"): {"pickup": ("parse_pickup_tables",)},
    ("pickup", "sliding-table"): {"pickup": ("parse_pickup_table",)},
    ("trainers", "class-gender"): {
        "trainers": (
            "parse_trainer_record",
            "resolve_trainer_variants",
            "FIRST_TRAINER_ID",
            *_STARTER_SELECTION_MEMBERS,
        )
    },
    ("trainers", "battle-mode"): {
        "trainers": (
            "parse_trainer_record",
            "resolve_trainer_variants",
            *_STARTER_SELECTION_MEMBERS,
        )
    },
    ("trainers", "pointer-party"): {
        "trainers": ("parse_trainer_record", "resolve_trainer_variants")
    },
    ("tutors", "overlay-table"): {"tutors": ("parse_tutor_move_table",)},
    ("tutors", "personal-archive"): {"tutors": ("parse_tutor_move_table",)},
    ("tutors", "flat-offset-table"): {
        "tutors": (
            "TUTOR_COMPATIBILITY_SIZE",
            "parse_tutor_compatibility",
            "parse_tutor_move_table",
        )
    },
    ("fossils", "script-pattern"): {"items": ("find_fossil_revival_script",)},
    ("static_encounters", "script-commands"): {
        "static_encounters": ("discover_static_encounters",)
    },
    ("egg_moves", "overlay-table"): {"egg_moves": ("parse_egg_move_table",)},
    ("egg_moves", "archive-table"): {"egg_moves": ("parse_egg_move_table",)},
    ("egg_moves", "species-archive"): {"egg_moves": ("parse_egg_move_set",)},
    ("egg_moves", "flat-offset-table"): {"egg_moves": ("parse_egg_move_table",)},
    ("item_archive", "arm9-map"): {"items": ("find_item_archive_members",)},
    ("machines", "profile-offset"): {
        "machines": ("MACHINE_COUNT", "TM_COUNT", "parse_machine_move_table")
    },
    ("machines", "binary-prefix"): {
        "machines": ("MACHINE_TABLE_LOCATOR", "parse_machine_move_table")
    },
}
# Formats whose members are only read when their dataset is supported.
_FORMAT_DATASET_KINDS: dict[str, str | None] = {
    "encounters": "encounters",
    "locations": "locations",
    "location_extraction": "locations",
    "pickup": None,
    "trainers": "trainers",
    "tutors": None,
    "fossils": "items",
    "static_encounters": "pokemon",
    "egg_moves": None,
    "item_archive": "items",
    "machines": None,
}
# Members read when a profile contract accepts an optional layout section.
_LAYOUT_REQUIRED_MEMBERS: dict[str, dict[str, tuple[str, ...]]] = {
    "npc_trades": {
        "trades": (
            "NPC_TRADE_INTERACTION_BY_ID",
            "parse_english_message_archive",
            "parse_npc_trade_record",
        )
    },
}
# Each capability's members are only read when its dataset is supported.
_CAPABILITY_DATASET_KINDS: dict[str, str | None] = {
    DETACHED_NPC_TRADES: None,
    COMPRESSED_CODE_BINARY: None,
    TRAINER_LOCATIONS: "trainers",
    TRAINER_SCRIPT_REFERENCES: "trainers",
    TAG_BATTLES: "trainers",
    REMATCH_TABLE: "trainers",
    DIFFICULTY_BRANCHES: "trainers",
    LOCATION_SPECIAL_VENDORS: "locations",
}
_CAPABILITY_MEMBERS: dict[str, dict[str, tuple[str, ...]]] = {
    DETACHED_NPC_TRADES: {},
    COMPRESSED_CODE_BINARY: {},
    TRAINER_LOCATIONS: {
        "trainers": (
            "ARCHIVE_MEMBER_NONE",
            "TRAINER_OBJECT_ID_OFFSET",
            "TRAINER_OBJECT_SCRIPT_END",
            "TRAINER_OBJECT_SCRIPT_START",
            "parse_object_events",
        )
    },
    TRAINER_SCRIPT_REFERENCES: {
        "trainers": (
            "CHECK_WON_BATTLE",
            "START_TRAINER_BATTLE",
            "parse_trainer_battle_commands",
        )
    },
    TAG_BATTLES: {
        "trainers": (
            "parse_staged_partner_battle_families",
            "parse_tag_battle_commands",
        )
    },
    REMATCH_TABLE: {"trainers": ("REMATCH_RECORD_SIZE", "parse_rematch_table")},
    DIFFICULTY_BRANCHES: {"trainers": ("parse_difficulty_branch_families",)},
    LOCATION_SPECIAL_VENDORS: {"locations": ("resolve_location_special_vendors",)},
}


def get_engine(engine: str) -> EngineAdapter:
    try:
        return _ENGINES[engine]
    except KeyError as error:
        raise DataSourceError(f"Unsupported engine: {engine!r}") from error


def register_engine(
    engine: str, adapter: EngineAdapter, *, validate: bool = True
) -> None:
    """Register an engine adapter under `engine`, replacing any existing entry.

    Intended for tests exercising the enrichment contract against a
    throwaway fake engine; real engines register themselves in `_ENGINES` above.
    """
    if validate:
        _validate_engine_adapter(engine, adapter)
    _ENGINES[engine] = adapter


def unregister_engine(engine: str) -> None:
    """Remove a previously registered engine, e.g. in a test's tearDown."""
    _ENGINES.pop(engine, None)


def _validate_engine_formats(engine: str, adapter: EngineAdapter) -> None:
    invalid_formats = [
        f"{name}={getattr(adapter.formats, name)!r}"
        for name, format_type in _FORMAT_TYPES.items()
        if getattr(adapter.formats, name) not in get_args(format_type)
    ]
    if invalid_formats:
        raise DataSourceError(
            f"Engine {engine!r} declares invalid formats: {', '.join(invalid_formats)}"
        )
    expected_location_shape = _LOCATION_EXTRACTION_SHAPES[
        adapter.formats.location_extraction
    ]
    if adapter.formats.locations != expected_location_shape:
        raise DataSourceError(
            f"Engine {engine!r} location extraction "
            f"{adapter.formats.location_extraction!r} requires normalized "
            f"shape {expected_location_shape!r}"
        )


def _required_members(adapter: EngineAdapter) -> dict[str, list[str]]:
    """Collect the members each concern must provide for this adapter."""
    required: dict[str, list[str]] = defaultdict(list)

    def require(members_by_concern: dict[str, tuple[str, ...]]) -> None:
        for concern, members in members_by_concern.items():
            required[concern].extend(members)

    for dataset, members_by_concern in _DATASET_REQUIRED_MEMBERS.items():
        if dataset in adapter.dataset_kinds:
            require(members_by_concern)
    for (field, format_name), members_by_concern in _FORMAT_REQUIRED_MEMBERS.items():
        dataset_kind = _FORMAT_DATASET_KINDS[field]
        if (dataset_kind is None or dataset_kind in adapter.dataset_kinds) and getattr(
            adapter.formats, field
        ) == format_name:
            require(members_by_concern)
    contract = adapter.profile_contract
    accepted_layout = contract.required_layout | contract.optional_layout
    for layout_key, members_by_concern in _LAYOUT_REQUIRED_MEMBERS.items():
        if layout_key in accepted_layout:
            require(members_by_concern)
    for capability in adapter.capabilities:
        dataset_kind = _CAPABILITY_DATASET_KINDS[capability]
        if dataset_kind is None or dataset_kind in adapter.dataset_kinds:
            require(_CAPABILITY_MEMBERS[capability])
    return required


def _validate_engine_adapter(engine: str, adapter: EngineAdapter) -> None:
    _validate_engine_formats(engine, adapter)
    if adapter.generation is not None and (
        not isinstance(adapter.generation, int) or adapter.generation < 1
    ):
        raise DataSourceError(
            f"Engine {engine!r} declares invalid generation: {adapter.generation!r}"
        )
    unknown = adapter.dataset_kinds - set(DATASET_KINDS)
    if unknown:
        raise DataSourceError(
            f"Engine {engine!r} declares unknown datasets: {', '.join(sorted(unknown))}"
        )
    unavailable_required = adapter.required_dataset_kinds - adapter.dataset_kinds
    if unavailable_required:
        raise DataSourceError(
            f"Engine {engine!r} requires unsupported datasets: "
            f"{', '.join(sorted(unavailable_required))}"
        )
    if "pokemon" not in adapter.dataset_kinds:
        raise DataSourceError(f"Engine {engine!r} must support the pokemon dataset")
    if "pokemon" not in adapter.required_dataset_kinds:
        raise DataSourceError(f"Engine {engine!r} must require the pokemon dataset")
    for dataset, dependencies in _DATASET_DEPENDENCIES.items():
        if dataset not in adapter.dataset_kinds:
            continue
        missing_dependencies = dependencies - adapter.dataset_kinds
        if missing_dependencies:
            raise DataSourceError(
                f"Engine {engine!r} dataset {dataset!r} requires supported "
                f"datasets: {', '.join(sorted(missing_dependencies))}"
            )

    unknown_capabilities = adapter.capabilities - set(_CAPABILITY_MEMBERS)
    if unknown_capabilities:
        raise DataSourceError(
            f"Engine {engine!r} declares unknown capabilities: "
            f"{', '.join(sorted(unknown_capabilities))}"
        )

    for concern, members in _required_members(adapter).items():
        namespace = getattr(adapter, concern)
        missing = sorted(
            {member for member in members if not hasattr(namespace, member)}
        )
        if missing:
            names = ", ".join(missing)
            raise DataSourceError(
                f"Engine {engine!r} {concern} concern is missing: {names}"
            )


for _engine_id, _adapter in _ENGINES.items():
    _validate_engine_adapter(_engine_id, _adapter)

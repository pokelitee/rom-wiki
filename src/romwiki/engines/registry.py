from __future__ import annotations

from dataclasses import dataclass
from types import ModuleType
from typing import Any, Literal, Protocol, get_args

import romwiki.engines.gen3.emerald as gen3_emerald
import romwiki.engines.gen3.frlg as gen3_frlg
import romwiki.engines.gen4.hgss as gen4_hgss
import romwiki.engines.gen4.platinum as gen4_platinum
import romwiki.engines.gen5.b2w2 as gen5_b2w2
import romwiki.engines.gen5.bw as gen5_bw
from romwiki.engines.profile_contracts import (
    GEN3_EMERALD_PROFILE_CONTRACT,
    GEN3_FRLG_PROFILE_CONTRACT,
    GEN4_HGSS_PROFILE_CONTRACT,
    GEN4_PLATINUM_PROFILE_CONTRACT,
    GEN5_B2W2_PROFILE_CONTRACT,
    GEN5_BW_PROFILE_CONTRACT,
    EngineProfileContract,
)
from romwiki.util.errors import DataSourceError

# Canonical engine identifiers used by registration and contract tests.
GEN3_FRLG_ENGINE = "gen3_frlg"
GEN3_EMERALD_ENGINE = "gen3_emerald"
GEN4_PLATINUM_ENGINE = "gen4_platinum"
GEN4_HGSS_ENGINE = "gen4_hgss"
GEN5_BW_ENGINE = "gen5_bw"
GEN5_B2W2_ENGINE = "gen5_b2w2"

EncounterFormat = Literal["unsupported", "conditional", "seasonal", "method-table"]
LocationFormat = Literal["unsupported", "event-map", "encounter-map"]
LocationExtractionFormat = Literal[
    "unsupported",
    "arm9-event-map",
    "arm9-encounter-map",
    "archive-encounter-map",
    "flat-header-segments",
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


class EngineConcern(Protocol):
    """Typed boundary for parser/constant namespaces owned by an engine."""

    def __getattr__(self, name: str) -> Any: ...


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

    Each field is the module (or object) providing that concern's parsers,
    constants, and record types. A pipeline module looks up the adapter for
    the current profile's engine and accesses names through it instead of
    importing a specific engine package directly.
    """

    personal: EngineConcern
    locations: EngineConcern
    trainers: EngineConcern
    encounters: EngineConcern
    evolutions: EngineConcern
    items: EngineConcern
    machines: EngineConcern
    moves: EngineConcern
    tutors: EngineConcern
    egg_moves: EngineConcern
    learnsets: EngineConcern
    reference_names: EngineConcern
    enrich: EngineConcern
    trainer_party: EngineConcern
    trades: EngineConcern
    marts: EngineConcern
    static_encounters: EngineConcern
    pickup: EngineConcern
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
    return EngineAdapter(
        **dict.fromkeys(_CONCERN_FIELDS, namespace),
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
        # Vertical slice: Pokémon personal data, moves, items, trainers,
        # abilities, encounters, and locations are implemented so far.
        # Unimplemented concerns are never accessed because
        # `dataset_kinds`/`formats` below declare nothing that would require
        # them (enforced by `_validate_engine_adapter`). Widen this entry's
        # formats as extraction work adds more Generation III domains.
        gen3_frlg,
        formats=EngineFormats(
            encounters="method-table",
            locations="encounter-map",
            location_extraction="flat-header-segments",
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
        # for the real-ROM cross-checks proving each shared fact). Widen
        # dataset_kinds as more Generation III domains are verified against
        # this ROM.
        gen3_emerald,
        formats=EngineFormats(
            encounters="method-table",
            locations="encounter-map",
            location_extraction="flat-header-segments",
            pickup="none",
            trainers="pointer-party",
            tutors="none",
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
        capabilities=frozenset({"detached-npc-trades"}),
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
        capabilities=frozenset({"detached-npc-trades"}),
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
        capabilities=frozenset({"detached-npc-trades"}),
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
    "flat-header-segments": "encounter-map",
}
_DATASET_REQUIRED_MEMBERS: dict[str, tuple[str, tuple[str, ...]]] = {
    "pokemon": ("personal", ("parse_personal_record", "PERSONAL_RECORD_COUNT")),
    "moves": ("moves", ("parse_move_record",)),
    "items": ("items", ("parse_item_record",)),
    "trainers": ("trainer_party", ("normalize_trainer_party_member",)),
}
_FORMAT_REQUIRED_MEMBERS: dict[tuple[str, str], tuple[str, ...]] = {
    ("encounters", "conditional"): ("parse_encounter_record",),
    ("encounters", "seasonal"): ("parse_encounter_entry",),
    ("encounters", "method-table"): ("parse_encounter_record",),
    ("locations", "event-map"): ("parse_map_headers",),
    ("locations", "encounter-map"): ("parse_map_header_table",),
    ("pickup", "split-table"): ("parse_pickup_tables",),
    ("pickup", "sliding-table"): ("parse_pickup_table",),
    ("trainers", "class-gender"): (
        "parse_trainer_record",
        "resolve_trainer_variants",
    ),
    ("trainers", "battle-mode"): (
        "parse_trainer_record",
        "resolve_trainer_variants",
    ),
    ("trainers", "pointer-party"): (
        "parse_trainer_record",
        "resolve_trainer_variants",
    ),
    ("tutors", "overlay-table"): ("parse_tutor_move_table",),
    ("tutors", "personal-archive"): ("parse_tutor_move_table",),
    ("tutors", "flat-offset-table"): ("parse_tutor_move_table",),
    ("egg_moves", "overlay-table"): ("parse_egg_move_table",),
    ("egg_moves", "archive-table"): ("parse_egg_move_table",),
    ("egg_moves", "species-archive"): ("parse_egg_move_set",),
    ("egg_moves", "flat-offset-table"): ("parse_egg_move_table",),
    ("item_archive", "arm9-map"): ("find_item_archive_members",),
    ("machines", "profile-offset"): ("parse_machine_move_table",),
    ("machines", "binary-prefix"): (
        "MACHINE_TABLE_LOCATOR",
        "parse_machine_move_table",
    ),
}
# Formats whose members are only read when their dataset is supported.
_FORMAT_DATASET_KINDS: dict[str, str | None] = {
    "encounters": "encounters",
    "locations": "locations",
    "pickup": None,
    "trainers": "trainers",
    "tutors": None,
    "egg_moves": None,
    "item_archive": "items",
    "machines": None,
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

    Intended for tests exercising the enrichment/rendering contract against a
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

    required: dict[str, tuple[str, ...]] = {
        concern: members
        for dataset, (concern, members) in _DATASET_REQUIRED_MEMBERS.items()
        if dataset in adapter.dataset_kinds
    }
    for (concern, format_name), members in _FORMAT_REQUIRED_MEMBERS.items():
        dataset_kind = _FORMAT_DATASET_KINDS[concern]
        if (dataset_kind is None or dataset_kind in adapter.dataset_kinds) and getattr(
            adapter.formats, concern
        ) == format_name:
            required[concern] = members
    if "items" in adapter.dataset_kinds and adapter.formats.fossils == "script-pattern":
        required["items"] = (*required["items"], "find_fossil_revival_script")
    if (
        "pokemon" in adapter.dataset_kinds
        and adapter.formats.static_encounters == "script-commands"
    ):
        required["static_encounters"] = ("discover_static_encounters",)
    for concern, members in required.items():
        namespace = getattr(adapter, "items" if concern == "item_archive" else concern)
        missing = [member for member in members if not hasattr(namespace, member)]
        if missing:
            names = ", ".join(missing)
            raise DataSourceError(
                f"Engine {engine!r} {concern} concern is missing: {names}"
            )


for _engine_id, _adapter in _ENGINES.items():
    _validate_engine_adapter(_engine_id, _adapter)

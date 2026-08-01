from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol

import romwiki.engines.gen4.dppt as gen4_dppt
import romwiki.engines.gen5.b2w2 as gen5_b2w2
import romwiki.engines.gen5.bw as gen5_bw
from romwiki.util.errors import DataSourceError

# Canonical engine-name strings, for the handful of pipeline/renderer call
# sites that must dispatch on which engine they're given a dataset for
# (encounters/locations/trainers have genuinely different record shapes per
# engine, unlike everything else, which dispatches generically through
# EngineAdapter). Referencing these constants instead of repeating string
# literals keeps that dispatch centralized on one source of truth.
GEN4_DPPT_ENGINE = "gen4_dppt"
GEN5_BW_ENGINE = "gen5_bw"
GEN5_B2W2_ENGINE = "gen5_b2w2"

EncounterFormat = Literal["conditional", "seasonal"]
LocationFormat = Literal["event-map", "encounter-map"]
PickupFormat = Literal["split-table", "sliding-table"]
TrainerFormat = Literal["class-gender", "battle-mode"]
TutorFormat = Literal["none", "overlay-table", "personal-archive"]
FossilFormat = Literal["none", "arm9-table", "script-pattern"]
StaticEncounterFormat = Literal["none", "script-commands"]


class EngineConcern(Protocol):
    """Typed boundary for parser/constant namespaces owned by an engine."""

    def __getattr__(self, name: str) -> Any: ...


@dataclass(frozen=True, slots=True)
class EngineFormats:
    encounters: EncounterFormat
    locations: LocationFormat
    pickup: PickupFormat
    trainers: TrainerFormat
    tutors: TutorFormat
    fossils: FossilFormat
    static_encounters: StaticEncounterFormat


@dataclass(frozen=True, slots=True)
class _EngineNamespaceOverlay:
    """Use family-specific facts while retaining verified shared Gen V facts."""

    primary: Any
    fallback: Any

    def __getattr__(self, name: str) -> Any:
        try:
            return getattr(self.primary, name)
        except AttributeError:
            return getattr(self.fallback, name)


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


_ENGINES: dict[str, EngineAdapter] = {
    GEN4_DPPT_ENGINE: EngineAdapter(
        personal=gen4_dppt,
        locations=gen4_dppt,
        trainers=gen4_dppt,
        encounters=gen4_dppt,
        evolutions=gen4_dppt,
        items=gen4_dppt,
        machines=gen4_dppt,
        moves=gen4_dppt,
        tutors=gen4_dppt,
        egg_moves=gen4_dppt,
        learnsets=gen4_dppt,
        reference_names=gen4_dppt,
        enrich=gen4_dppt,
        trainer_party=gen4_dppt,
        trades=gen4_dppt,
        marts=gen4_dppt,
        static_encounters=gen4_dppt,
        pickup=gen4_dppt,
        formats=EngineFormats(
            encounters="conditional",
            locations="event-map",
            pickup="split-table",
            trainers="class-gender",
            tutors="overlay-table",
            fossils="arm9-table",
            static_encounters="none",
        ),
        generation=4,
        presentation_features=frozenset({"contests"}),
    ),
    GEN5_BW_ENGINE: EngineAdapter(
        personal=gen5_bw,
        locations=gen5_bw,
        trainers=gen5_bw,
        encounters=gen5_bw,
        evolutions=gen5_bw,
        items=gen5_bw,
        machines=gen5_bw,
        moves=gen5_bw,
        tutors=gen5_bw,
        egg_moves=gen5_bw,
        learnsets=gen5_bw,
        reference_names=gen5_bw,
        enrich=gen5_bw,
        trainer_party=gen5_bw,
        trades=gen5_bw,
        marts=gen5_bw,
        static_encounters=gen5_bw,
        pickup=gen5_bw,
        formats=EngineFormats(
            encounters="seasonal",
            locations="encounter-map",
            pickup="sliding-table",
            trainers="battle-mode",
            tutors="none",
            fossils="script-pattern",
            static_encounters="script-commands",
        ),
        generation=5,
        presentation_features=frozenset(
            {
                "post-battle-healing",
                "victory-items",
            }
        ),
        capabilities=frozenset({"detached-npc-trades"}),
    ),
    GEN5_B2W2_ENGINE: EngineAdapter(
        personal=gen5_b2w2,
        locations=_EngineNamespaceOverlay(gen5_b2w2, gen5_bw),
        trainers=gen5_bw,
        encounters=gen5_bw,
        evolutions=gen5_bw,
        items=_EngineNamespaceOverlay(gen5_b2w2, gen5_bw),
        machines=gen5_bw,
        moves=gen5_bw,
        tutors=gen5_b2w2,
        egg_moves=gen5_bw,
        learnsets=gen5_bw,
        reference_names=_EngineNamespaceOverlay(gen5_b2w2, gen5_bw),
        enrich=_EngineNamespaceOverlay(gen5_b2w2, gen5_bw),
        trainer_party=gen5_bw,
        trades=gen5_bw,
        marts=_EngineNamespaceOverlay(gen5_b2w2, gen5_bw),
        static_encounters=gen5_b2w2,
        pickup=gen5_bw,
        formats=EngineFormats(
            encounters="seasonal",
            locations="encounter-map",
            pickup="sliding-table",
            trainers="battle-mode",
            tutors="personal-archive",
            fossils="none",
            static_encounters="script-commands",
        ),
        generation=5,
        presentation_features=frozenset(
            {
                "post-battle-healing",
                "victory-items",
            }
        ),
        capabilities=frozenset({"detached-npc-trades"}),
    ),
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


def _validate_engine_adapter(engine: str, adapter: EngineAdapter) -> None:
    required = {
        "personal": ("parse_personal_record", "PERSONAL_RECORD_COUNT"),
        "moves": ("parse_move_record",),
        "items": ("parse_item_record",),
        "learnsets": ("parse_level_up_learnset",),
        "evolutions": ("parse_evolution_record",),
        "machines": ("parse_machine_move_table",),
        "trainer_party": ("normalize_trainer_party_member",),
    }
    format_required = {
        ("encounters", "conditional"): ("parse_encounter_record",),
        ("encounters", "seasonal"): ("parse_encounter_entry",),
        ("locations", "event-map"): ("parse_map_headers",),
        ("locations", "encounter-map"): ("parse_map_header_table",),
        ("pickup", "split-table"): ("parse_pickup_tables",),
        ("pickup", "sliding-table"): ("parse_pickup_table",),
        ("trainers", "class-gender"): ("parse_trainer_record",),
        ("trainers", "battle-mode"): ("parse_trainer_record",),
        ("tutors", "overlay-table"): ("parse_tutor_move_table",),
        ("tutors", "personal-archive"): ("parse_tutor_move_table",),
    }
    for (concern, format_name), members in format_required.items():
        if getattr(adapter.formats, concern) == format_name:
            required[concern] = members
    if adapter.formats.fossils == "script-pattern":
        required["items"] = (*required["items"], "find_fossil_revival_script")
    if adapter.formats.static_encounters == "script-commands":
        required["static_encounters"] = ("discover_static_encounters",)
    for concern, members in required.items():
        namespace = getattr(adapter, concern)
        missing = [member for member in members if not hasattr(namespace, member)]
        if missing:
            names = ", ".join(missing)
            raise DataSourceError(
                f"Engine {engine!r} {concern} concern is missing: {names}"
            )


for _engine_id, _adapter in _ENGINES.items():
    _validate_engine_adapter(_engine_id, _adapter)

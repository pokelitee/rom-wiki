from __future__ import annotations

import json
import logging
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, cast

from romwiki.engines.registry import DETACHED_NPC_TRADES, get_engine
from romwiki.pipeline.build.fingerprint import (
    combined_extraction_source_fingerprint,
    profile_fingerprint,
)
from romwiki.pipeline.build.sections import dataset_enabled, enabled_dataset_kinds
from romwiki.pipeline.enrichment.abilities import build_ability_dataset
from romwiki.pipeline.enrichment.encounters import enrich_encounter_dataset
from romwiki.pipeline.enrichment.features import attach_features
from romwiki.pipeline.enrichment.items import build_item_dataset
from romwiki.pipeline.enrichment.locations import enrich_location_dataset
from romwiki.pipeline.enrichment.moves import enrich_move_dataset
from romwiki.pipeline.enrichment.pokemon import enrich_personal_dataset
from romwiki.pipeline.enrichment.trades import enrich_npc_trade_dataset
from romwiki.pipeline.enrichment.trainers import enrich_trainer_dataset
from romwiki.pipeline.extraction.egg_moves import extract_egg_move_dataset
from romwiki.pipeline.extraction.encounters.dispatcher import extract_encounter_dataset
from romwiki.pipeline.extraction.evolutions import extract_evolution_dataset
from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.pipeline.extraction.items import extract_item_dataset
from romwiki.pipeline.extraction.learnsets import extract_learnset_dataset
from romwiki.pipeline.extraction.locations.dispatcher import extract_location_dataset
from romwiki.pipeline.extraction.machines import extract_machine_dataset
from romwiki.pipeline.extraction.marts import extract_mart_dataset
from romwiki.pipeline.extraction.moves import extract_move_dataset
from romwiki.pipeline.extraction.personal import extract_personal_dataset
from romwiki.pipeline.extraction.pickup import extract_pickup_dataset
from romwiki.pipeline.extraction.static_encounters import (
    extract_static_encounter_dataset,
)
from romwiki.pipeline.extraction.trades import extract_npc_trade_dataset
from romwiki.pipeline.extraction.trainers.dispatcher import extract_trainer_dataset
from romwiki.pipeline.extraction.tutors import extract_tutor_dataset
from romwiki.schema.datasets import validate_dataset_envelope
from romwiki.schema.enriched import (
    AbilityDataset,
    EncounterDataset,
    ItemDataset,
    LocationDataset,
    MoveDataset,
    PokemonDataset,
    TrainerDataset,
)
from romwiki.schema.versions import (
    CACHE_MANIFEST_SCHEMA_VERSION,
    RAW_SCHEMA_VERSION_BY_CACHE_KEY,
)
from romwiki.sources import PokeDBGeneration
from romwiki.util.errors import DataSourceError, ProfileError
from romwiki.util.json_io import json_round_trip, write_json_atomic

CACHE_REVISION = 6
_LOG = logging.getLogger("romwiki")


class GameBuildContext:
    def __init__(
        self,
        result: InspectionResult,
        pokedb: PokeDBGeneration,
        *,
        cache_root: Path | None = None,
        refresh: bool = False,
        source_fingerprint: str | Mapping[str, str] | None = None,
    ) -> None:
        if result.match is None:
            raise ProfileError("A matched profile is required for a game build")
        self.result = result
        self.profile = result.match.profile
        self.pokedb = pokedb
        self.cache_root = cache_root
        self.refresh = refresh
        self._source_fingerprint_override = source_fingerprint
        self._values: dict[str, dict[str, Any]] = {}
        self._enriched: dict[str, Mapping[str, Any]] = {}
        self._cache_manifest = self._read_manifest()
        self._initial_cache_valid = self._manifest_valid(self._cache_manifest)
        fingerprints = self._cache_manifest.get("source_fingerprints", {})
        self._cached_source_fingerprints = (
            dict(fingerprints)
            if self._initial_cache_valid and isinstance(fingerprints, dict)
            else {}
        )

    def personal_raw(self) -> dict[str, Any]:
        return self._raw("pokemon/personal", extract_personal_dataset)

    # The five accessors below back optional enrichment inputs for pokemon()/
    # abilities() (learnsets, evolutions, TM/HM compatibility, tutors, egg
    # moves): enrich_personal_dataset and build_ability_dataset already accept
    # each as None, so a profile that doesn't configure one (e.g. an engine's
    # first vertical slice, which implements personal data before these
    # datasets) gets a Pokémon section without that detail instead of a hard
    # failure.
    def learnsets_raw(self) -> dict[str, Any] | None:
        if (
            "learnsets" not in self.profile.layout
            and "learnset_offset" not in self.profile.parameters
        ):
            return None
        return self._raw("pokemon/learnsets", extract_learnset_dataset)

    def egg_moves_raw(self) -> dict[str, Any] | None:
        if (
            "egg_moves" not in self.profile.layout
            and "egg_move_offset" not in self.profile.parameters
        ):
            return None
        return self._raw("pokemon/egg-moves", extract_egg_move_dataset)

    def evolutions_raw(self) -> dict[str, Any] | None:
        if (
            "evolutions" not in self.profile.layout
            and "evolution_offset" not in self.profile.parameters
        ):
            return None
        return self._raw("pokemon/evolutions", extract_evolution_dataset)

    def machines_raw(self) -> dict[str, Any] | None:
        machine_format = get_engine(self.profile.engine).formats.machines
        if (
            "machine_move_offset" not in self.profile.parameters
            and "machine_move_prefix" not in self.profile.parameters
            and machine_format == "none"
        ):
            return None
        return self._raw("machines/raw", extract_machine_dataset)

    def tutors_raw(self) -> dict[str, Any] | None:
        if "tutor_move_offset" not in self.profile.parameters:
            return None
        return self._raw("tutors/raw", extract_tutor_dataset)

    def pickup_raw(self) -> dict[str, Any] | None:
        # DS profiles locate Pickup through an overlay, Generation III ones
        # through flat offsets.
        if not any(
            parameter in self.profile.parameters
            for parameter in (
                "pickup_overlay_id",
                "pickup_common_items_offset",
                "pickup_items_offset",
            )
        ):
            return None
        return self._raw("pickup/raw", extract_pickup_dataset)

    # moves_raw/encounters_raw are deliberately NOT gated like the accessors
    # above: Moves and Encounters are mandatory dataset kinds every profile
    # must define (unlike the optional enrichment inputs above, some of which
    # a given engine may never implement -- e.g. Gen5 BW has no move tutors
    # at all). A profile missing one of their layout keys is a real
    # configuration error, so it should surface as the extractor's own clear
    # ProfileError rather than be silently treated as an absent section.
    def moves_raw(self) -> dict[str, Any]:
        return self._raw("moves/raw", extract_move_dataset)

    def encounters_raw(self) -> dict[str, Any]:
        return self._raw("encounters/raw", extract_encounter_dataset)

    def trainers_raw(self) -> dict[str, Any] | None:
        if not dataset_enabled(self.profile, "trainers"):
            return None
        return self._raw("trainers/raw", extract_trainer_dataset)

    def locations_raw(self) -> dict[str, Any] | None:
        if not dataset_enabled(self.profile, "locations"):
            return None
        return self._raw(
            "locations/raw",
            lambda result: extract_location_dataset(
                result,
                trainer_dataset=self.trainers_raw(),
                static_encounter_dataset=self.static_encounters_raw(),
                item_dataset=self.items_raw(),
                mart_dataset=self.marts_raw(),
                trade_dataset=self.trades_raw(),
            ),
            # The location record embeds these datasets' own output (trainer
            # rosters, static encounters, shop/trade details), not just what
            # extract_location_dataset's own module imports -- so its cache
            # must invalidate when any of them changes too.
            source=(
                extract_location_dataset,
                extract_trainer_dataset,
                extract_static_encounter_dataset,
                extract_item_dataset,
                extract_mart_dataset,
                extract_npc_trade_dataset,
            ),
        )

    # Items is normally as mandatory as moves/encounters (see the comment
    # above), but -- like trainers_raw/locations_raw -- it's gated on the
    # engine's own declared dataset support: a personal-data-only vertical
    # slice (an engine's first onboarding step) has no items domain yet, and
    # pokemon()/locations_raw() below already treat a missing item dataset as
    # an absent, optional enrichment input rather than a hard failure.
    def items_raw(self) -> dict[str, Any] | None:
        if not dataset_enabled(self.profile, "items"):
            return None
        return self._raw("items/raw", extract_item_dataset)

    def trades_raw(self) -> dict[str, Any] | None:
        # Some engines expose trades through location records; others provide
        # a detached archive that must be attached to items separately.
        engine = get_engine(self.profile.engine)
        if (
            DETACHED_NPC_TRADES not in engine.capabilities
            or "npc_trades" not in self.profile.layout
        ):
            return None
        return self._raw("trades/raw", extract_npc_trade_dataset)

    def marts_raw(self) -> dict[str, Any] | None:
        if (
            "shop_item_overlay_id" not in self.profile.parameters
            and "shop_catalog_locator" not in self.profile.parameters
            and "shop_items" not in self.profile.layout
        ):
            return None
        return self._raw("marts/raw", extract_mart_dataset)

    def static_encounters_raw(self) -> dict[str, Any] | None:
        if get_engine(self.profile.engine).formats.static_encounters == "none":
            return None
        return self._raw("static-encounters/raw", extract_static_encounter_dataset)

    def trades(self) -> dict[str, Any] | None:
        dataset = self.trades_raw()
        if dataset is None:
            return None
        return self._memo(
            "trades/enriched",
            lambda: enrich_npc_trade_dataset(
                dataset, self.pokemon(), self.locations_raw()
            ),
        )

    def pokemon(self) -> PokemonDataset:
        return attach_features(
            self._memo(
                "pokemon/enriched",
                lambda: enrich_personal_dataset(
                    self.personal_raw(),
                    self.pokedb,
                    self.learnsets_raw(),
                    self.evolutions_raw(),
                    self.machines_raw(),
                    self.tutors_raw(),
                    self.egg_moves_raw(),
                    self.static_encounters_raw(),
                    item_dataset=self.items_raw(),
                    move_dataset=self.moves_raw(),
                    type_names=self.profile.type_names,
                    move_names=self.profile.move_names,
                    sprite_version=self.profile.sprite_version,
                    reference_version=self.profile.base_game,
                ),
            ),
            self.profile,
        )

    def abilities(self) -> AbilityDataset:
        return attach_features(
            self._memo(
                "abilities/enriched",
                lambda: build_ability_dataset(
                    self.pokemon(),
                    self.pokedb,
                    self.pickup_raw(),
                    reference_version=self.profile.base_game,
                ),
            ),
            self.profile,
        )

    def moves(self) -> MoveDataset:
        return attach_features(
            self._memo(
                "moves/enriched",
                lambda: enrich_move_dataset(
                    self.moves_raw(),
                    self.pokedb,
                    self.machines_raw(),
                    self.tutors_raw(),
                    self.egg_moves_raw(),
                    type_names=self.profile.type_names,
                    move_names=self.profile.move_names,
                    reference_version=self.profile.base_game,
                ),
            ),
            self.profile,
        )

    def encounters(self) -> EncounterDataset:
        return attach_features(
            self._memo(
                "encounters/enriched",
                lambda: enrich_encounter_dataset(
                    self.encounters_raw(),
                    self.pokedb,
                    sprite_version=self.profile.sprite_version,
                ),
            ),
            self.profile,
        )

    def trainers(self) -> TrainerDataset | None:
        trainers_raw = self.trainers_raw()
        if trainers_raw is None:
            return None
        return attach_features(
            self._memo(
                "trainers/enriched",
                lambda: enrich_trainer_dataset(
                    trainers_raw,
                    self.pokedb,
                    pokemon_dataset=self.pokemon(),
                    move_dataset=self.moves(),
                    move_names=self.profile.move_names,
                    sprite_version=self.profile.sprite_version,
                    reference_version=self.profile.base_game,
                ),
            ),
            self.profile,
        )

    def locations(self) -> LocationDataset | None:
        dataset = self.locations_raw()
        if dataset is None:
            return None
        return attach_features(
            self._memo("locations/enriched", lambda: enrich_location_dataset(dataset)),
            self.profile,
        )

    def items(self) -> ItemDataset:
        return attach_features(
            self._memo(
                "items/enriched",
                self._build_item_dataset,
            ),
            self.profile,
        )

    def _build_item_dataset(self) -> ItemDataset:
        # Only called when dataset_enabled(profile, "items") is true (see
        # items_raw() above and its callers), so a None items_raw() here
        # would be a real bug, not a normal engine-capability gap.
        dataset = self.items_raw()
        if dataset is None:
            raise ProfileError(
                f"Profile {self.profile.id} does not support an items dataset"
            )
        return build_item_dataset(
            dataset,
            self.pokedb,
            self.pokemon(),
            self.trainers(),
            self.locations(),
            # Unlike moves_raw/encounters_raw (mandatory dataset kinds for
            # every engine that declares "encounters" support at all),
            # gen3_frlg doesn't implement encounters yet -- gated the same
            # way trainers()/locations() already are, rather than crashing
            # on a domain this engine's items build doesn't need.
            encounter_dataset=(
                self.encounters()
                if dataset_enabled(self.profile, "encounters")
                else None
            ),
            trade_dataset=self.trades(),
            mart_dataset=self.marts_raw(),
            reference_version=self.profile.base_game,
        )

    def all_datasets(self) -> dict[str, Mapping[str, Any]]:
        return {
            kind: getattr(self, kind)() for kind in enabled_dataset_kinds(self.profile)
        }

    def _raw(
        self,
        key: str,
        extractor: Callable[[InspectionResult], dict[str, Any]],
        *,
        source: Callable[..., Any] | tuple[Callable[..., Any], ...] | None = None,
    ) -> dict[str, Any]:
        if key in self._values:
            return self._values[key]
        path = self.cache_root / f"{key}.json" if self.cache_root else None
        source_fingerprint = None
        if path is not None:
            source_fingerprint = self._source_fingerprint(key, source or extractor)
            if not self.refresh:
                cached = self._read_cache(key, path, source_fingerprint)
                if cached is not None:
                    _LOG.debug("Extraction cache hit for %s: %s", self.profile.id, key)
                    self._values[key] = cached
                    return cached
            reason = "refresh" if self.refresh else "miss"
            _LOG.debug("Extraction cache %s for %s: %s", reason, self.profile.id, key)
        _LOG.debug("Extracting %s for %s", key, self.profile.id)
        # Cache hits are JSON-decoded, so fresh extractions take the same form
        # (lists, string keys); otherwise rendered pages and comparisons would
        # depend on whether this run happened to refresh the cache.
        value = json_round_trip(extractor(self.result))
        validate_dataset_envelope(value, context=key)
        self._values[key] = value
        if path is not None:
            # Unsorted, because renderers present some mappings (shard costs,
            # dual-slot games) in the order the extractor produced them.
            write_json_atomic(path, value, sort_keys=False, compact=True)
            assert source_fingerprint is not None
            self._write_manifest(key, source_fingerprint)
            _LOG.debug("Extraction cache updated for %s: %s", self.profile.id, key)
        return value

    def _memo[DatasetT: Mapping[str, Any]](
        self, key: str, factory: Callable[[], DatasetT]
    ) -> DatasetT:
        if key not in self._enriched:
            self._enriched[key] = factory()
            validate_dataset_envelope(self._enriched[key], context=key)
        return cast(DatasetT, self._enriched[key])

    def _read_cache(
        self, key: str, path: Path, source_fingerprint: str
    ) -> dict[str, Any] | None:
        if not self._initial_cache_valid or not path.is_file():
            return None
        if self._cached_source_fingerprints.get(key) != source_fingerprint:
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, OSError) as error:
            _LOG.warning("Ignoring unreadable extraction cache %s: %s", path, error)
            return None
        if not isinstance(value, dict):
            _LOG.warning("Ignoring extraction cache %s: not a JSON object", path)
            return None
        if value.get("schema_version") != RAW_SCHEMA_VERSION_BY_CACHE_KEY[key]:
            return None
        try:
            validate_dataset_envelope(value, context=key)
        except DataSourceError as error:
            _LOG.warning("Ignoring extraction cache %s: %s", path, error)
            return None
        if value["source"].get("rom_sha256") != self.result.image.hashes.sha256:
            return None
        return value

    def _read_manifest(self) -> dict[str, Any]:
        if self.cache_root is None:
            return {}
        path = self.cache_root / "manifest.json"
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        return value if isinstance(value, dict) else {}

    def _manifest_valid(self, value: dict[str, Any]) -> bool:
        if not value:
            return False
        return all(
            value.get(key) == expected
            for key, expected in self._manifest_header().items()
        )

    def _write_manifest(self, key: str, source_fingerprint: str) -> None:
        if self.cache_root is not None:
            self._cached_source_fingerprints[key] = source_fingerprint
            write_json_atomic(
                self.cache_root / "manifest.json", self._manifest(), compact=True
            )

    def _manifest(self) -> dict[str, Any]:
        return {
            **self._manifest_header(),
            "source_fingerprints": dict(
                sorted(self._cached_source_fingerprints.items())
            ),
        }

    def _manifest_header(self) -> dict[str, Any]:
        return {
            "schema_version": CACHE_MANIFEST_SCHEMA_VERSION,
            "cache_revision": CACHE_REVISION,
            "profile": self.profile.id,
            "profile_fingerprint": profile_fingerprint(self.profile),
            "rom_sha256": self.result.image.hashes.sha256,
        }

    def _source_fingerprint(
        self, key: str, source: Callable[..., Any] | tuple[Callable[..., Any], ...]
    ) -> str:
        override = self._source_fingerprint_override
        if isinstance(override, str):
            return override
        if override is not None:
            return override[key]
        sources = source if isinstance(source, tuple) else (source,)
        return combined_extraction_source_fingerprint(
            self.profile.engine,
            tuple(one.__module__ for one in sources),
            key,
        )

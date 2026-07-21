from __future__ import annotations

from collections.abc import Callable
import json
from pathlib import Path
from typing import Any

from romwiki.errors import ProfileError
from romwiki.pipeline.abilities import build_ability_dataset
from romwiki.pipeline.encounters import extract_encounter_dataset
from romwiki.pipeline.egg_moves import extract_egg_move_dataset
from romwiki.pipeline.enrich import (
    enrich_encounter_dataset,
    enrich_move_dataset,
    enrich_personal_dataset,
    enrich_trainer_dataset,
)
from romwiki.pipeline.evolutions import extract_evolution_dataset
from romwiki.pipeline.items import build_item_dataset, extract_item_dataset
from romwiki.pipeline.learnsets import extract_learnset_dataset
from romwiki.pipeline.locations import extract_location_dataset
from romwiki.pipeline.machines import extract_machine_dataset
from romwiki.pipeline.moves import extract_move_dataset
from romwiki.pipeline.personal import extract_personal_dataset
from romwiki.pipeline.trainers import extract_trainer_dataset
from romwiki.pipeline.tutors import extract_tutor_dataset
from romwiki.pipeline.identify import InspectionResult
from romwiki.sources import PokeDBGeneration


BASELINE_CACHE_REVISION = 1


class GameBuildContext:
    def __init__(
        self,
        result: InspectionResult,
        pokedb: PokeDBGeneration,
        *,
        cache_root: Path | None = None,
        refresh: bool = False,
    ) -> None:
        if result.match is None:
            raise ProfileError("A matched profile is required for a game build")
        self.result = result
        self.profile = result.match.profile
        self.pokedb = pokedb
        self.cache_root = cache_root
        self.refresh = refresh
        self._values: dict[str, dict[str, Any]] = {}

    def personal_raw(self) -> dict[str, Any]:
        return self._raw("pokemon/personal", extract_personal_dataset)

    def learnsets_raw(self) -> dict[str, Any]:
        return self._raw("pokemon/learnsets", extract_learnset_dataset)

    def egg_moves_raw(self) -> dict[str, Any]:
        return self._raw("pokemon/egg-moves", extract_egg_move_dataset)

    def evolutions_raw(self) -> dict[str, Any]:
        return self._raw("pokemon/evolutions", extract_evolution_dataset)

    def machines_raw(self) -> dict[str, Any]:
        return self._raw("machines/raw", extract_machine_dataset)

    def tutors_raw(self) -> dict[str, Any]:
        return self._raw("tutors/raw", extract_tutor_dataset)

    def moves_raw(self) -> dict[str, Any]:
        return self._raw("moves/raw", extract_move_dataset)

    def encounters_raw(self) -> dict[str, Any]:
        return self._raw("encounters/raw", extract_encounter_dataset)

    def trainers_raw(self) -> dict[str, Any]:
        return self._raw("trainers/raw", extract_trainer_dataset)

    def locations_raw(self) -> dict[str, Any]:
        return self._raw(
            "locations/raw",
            lambda result: extract_location_dataset(
                result, trainer_dataset=self.trainers_raw()
            ),
        )

    def items_raw(self) -> dict[str, Any]:
        return self._raw("items/raw", extract_item_dataset)

    def pokemon(self) -> dict[str, Any]:
        return self._memo(
            "pokemon/enriched",
            lambda: enrich_personal_dataset(
                self.personal_raw(),
                self.pokedb,
                self.learnsets_raw(),
                self.evolutions_raw(),
                self.machines_raw(),
                self.tutors_raw(),
                self.egg_moves_raw(),
                type_names=self.profile.type_names,
                move_names=self.profile.move_names,
                sprite_version=self.profile.sprite_version,
                reference_version=self.profile.base_game,
            ),
        )

    def abilities(self) -> dict[str, Any]:
        return self._memo(
            "abilities/enriched",
            lambda: build_ability_dataset(self.pokemon(), self.pokedb),
        )

    def moves(self) -> dict[str, Any]:
        return self._memo(
            "moves/enriched",
            lambda: enrich_move_dataset(
                self.moves_raw(),
                self.pokedb,
                self.machines_raw(),
                self.tutors_raw(),
                self.egg_moves_raw(),
                type_names=self.profile.type_names,
                move_names=self.profile.move_names,
            ),
        )

    def encounters(self) -> dict[str, Any]:
        return self._memo(
            "encounters/enriched",
            lambda: enrich_encounter_dataset(self.encounters_raw(), self.pokedb),
        )

    def trainers(self) -> dict[str, Any]:
        return self._memo(
            "trainers/enriched",
            lambda: enrich_trainer_dataset(
                self.trainers_raw(),
                self.pokedb,
                move_names=self.profile.move_names,
            ),
        )

    def locations(self) -> dict[str, Any]:
        return self.locations_raw()

    def items(self) -> dict[str, Any]:
        return self._memo(
            "items/enriched",
            lambda: build_item_dataset(
                self.items_raw(),
                self.pokedb,
                self.pokemon(),
                self.trainers(),
                self.locations(),
            ),
        )

    def all_datasets(self) -> dict[str, dict[str, Any]]:
        return {
            "pokemon": self.pokemon(),
            "abilities": self.abilities(),
            "moves": self.moves(),
            "items": self.items(),
            "encounters": self.encounters(),
            "trainers": self.trainers(),
            "locations": self.locations(),
        }

    def _raw(
        self,
        key: str,
        extractor: Callable[[InspectionResult], dict[str, Any]],
    ) -> dict[str, Any]:
        if key in self._values:
            return self._values[key]
        path = self.cache_root / f"{key}.json" if self.cache_root else None
        if path is not None and not self.refresh:
            cached = self._read_cache(path)
            if cached is not None:
                self._values[key] = cached
                return cached
        value = extractor(self.result)
        self._values[key] = value
        if path is not None:
            _write_json(path, value)
            self._write_manifest()
        return value

    def _memo(
        self, key: str, factory: Callable[[], dict[str, Any]]
    ) -> dict[str, Any]:
        if key not in self._values:
            self._values[key] = factory()
        return self._values[key]

    def _read_cache(self, path: Path) -> dict[str, Any] | None:
        if not self._manifest_valid() or not path.is_file():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        source = value.get("source", {}) if isinstance(value, dict) else {}
        if value.get("schema_version") != 1:
            return None
        if source.get("rom_sha256") != self.result.image.hashes.sha256:
            return None
        return value

    def _manifest_valid(self) -> bool:
        if self.cache_root is None:
            return False
        path = self.cache_root / "manifest.json"
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return False
        return value == self._manifest()

    def _write_manifest(self) -> None:
        if self.cache_root is not None:
            _write_json(self.cache_root / "manifest.json", self._manifest())

    def _manifest(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "cache_revision": BASELINE_CACHE_REVISION,
            "profile": self.profile.id,
            "rom_sha256": self.result.image.hashes.sha256,
        }


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)

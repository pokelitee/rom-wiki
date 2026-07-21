from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from romwiki.util.errors import DataSourceError, ProfileError
from romwiki.pipeline.build_context import GameBuildContext
from romwiki.pipeline.comparisons import compare_datasets
from romwiki.pipeline.identify import InspectionResult
from romwiki.sources import PokeDBGeneration


DATASET_KINDS = (
    "pokemon",
    "abilities",
    "moves",
    "items",
    "encounters",
    "trainers",
    "locations",
)


@dataclass(frozen=True, slots=True)
class DatasetBuild:
    current: dict[str, Any]
    baseline: dict[str, Any] | None
    comparison: dict[str, Any] | None


class GameBuildWorkflow:
    def __init__(
        self,
        current: InspectionResult,
        pokedb: PokeDBGeneration,
        *,
        baseline: InspectionResult | None = None,
        baseline_cache_root: Path = Path("build/data/baselines"),
        refresh_baseline: bool = False,
    ) -> None:
        self.current = GameBuildContext(current, pokedb)
        self.baseline = None
        if baseline is not None:
            if baseline.match is None:
                raise ProfileError("A matched baseline profile is required")
            cache = baseline_cache_root / baseline.match.profile.id
            self.baseline = GameBuildContext(
                baseline,
                pokedb,
                cache_root=cache,
                refresh=refresh_baseline,
            )

    def build(self, kind: str) -> DatasetBuild:
        if kind not in DATASET_KINDS:
            choices = ", ".join(DATASET_KINDS)
            raise DataSourceError(
                f"Unsupported build dataset {kind!r}; choose from {choices}"
            )
        baseline = self._dataset(self.baseline, kind) if self.baseline else None
        current = self._dataset(self.current, kind)
        comparison = compare_datasets(current, baseline) if baseline else None
        return DatasetBuild(current, baseline, comparison)

    def build_all(self) -> dict[str, DatasetBuild]:
        baselines = (
            {
                kind: self._dataset(self.baseline, kind)
                for kind in DATASET_KINDS
            }
            if self.baseline
            else {}
        )
        currents = {
            kind: self._dataset(self.current, kind) for kind in DATASET_KINDS
        }
        return {
            kind: DatasetBuild(
                currents[kind],
                baselines.get(kind),
                (
                    compare_datasets(currents[kind], baselines[kind])
                    if kind in baselines
                    else None
                ),
            )
            for kind in DATASET_KINDS
        }

    @staticmethod
    def _dataset(
        context: GameBuildContext | None, kind: str
    ) -> dict[str, Any]:
        if context is None:
            raise DataSourceError("Dataset context is required")
        factory = getattr(context, kind)
        return factory()

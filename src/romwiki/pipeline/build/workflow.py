from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from romwiki.engines.registry import DATASET_KINDS
from romwiki.pipeline.build.context import GameBuildContext
from romwiki.pipeline.build.sections import (
    describe_section_mismatch,
    enabled_dataset_kinds,
)
from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.pipeline.transforms.comparisons import compare_datasets
from romwiki.sources import PokeDBGeneration
from romwiki.util.errors import DataSourceError, ProfileError

_LOG = logging.getLogger("romwiki")


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
        baseline_cache_root: Path | None = Path("build/data/baselines"),
        refresh_baseline: bool = False,
        current_cache_root: Path | None = None,
        refresh_current: bool = False,
    ) -> None:
        current_cache = None
        if current_cache_root is not None:
            if current.match is None:
                raise ProfileError("A matched profile is required for a game build")
            current_cache = current_cache_root / current.match.profile.id
        self.current = GameBuildContext(
            current,
            pokedb,
            cache_root=current_cache,
            refresh=refresh_current,
        )
        self.baseline = None
        if baseline is not None:
            if baseline.match is None:
                raise ProfileError("A matched baseline profile is required")
            cache = (
                baseline_cache_root / baseline.match.profile.id
                if baseline_cache_root is not None
                else None
            )
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
        current_kinds = enabled_dataset_kinds(self.current.profile)
        if kind not in current_kinds:
            raise DataSourceError(
                f"Profile {self.current.profile.id!r} does not enable the "
                f"optional {kind!r} dataset section"
            )
        if self.baseline is not None:
            self._validate_matching_sections(current_kinds)
        baseline = self._dataset(self.baseline, kind) if self.baseline else None
        current = self._dataset(self.current, kind)
        comparison = compare_datasets(current, baseline) if baseline else None
        return DatasetBuild(current, baseline, comparison)

    def build_all(self) -> dict[str, DatasetBuild]:
        kinds = enabled_dataset_kinds(self.current.profile)
        if self.baseline is not None:
            self._validate_matching_sections(kinds)
        baselines = (
            {kind: self._dataset(self.baseline, kind) for kind in kinds}
            if self.baseline
            else {}
        )
        currents = {kind: self._dataset(self.current, kind) for kind in kinds}
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
            for kind in kinds
        }

    def _validate_matching_sections(self, current_kinds: tuple[str, ...]) -> None:
        if self.baseline is None:
            return
        baseline_kinds = enabled_dataset_kinds(self.baseline.profile)
        if baseline_kinds == current_kinds:
            return
        enabled = {
            self.current.profile.id: current_kinds,
            self.baseline.profile.id: baseline_kinds,
        }
        raise ProfileError(
            "Current and baseline profiles enable different dataset sections: "
            f"{describe_section_mismatch(enabled)}"
        )

    @staticmethod
    def _dataset(context: GameBuildContext | None, kind: str) -> dict[str, Any]:
        if context is None:
            raise DataSourceError("Dataset context is required")
        _LOG.info("Preparing %s dataset for %s", kind, context.profile.id)
        factory = getattr(context, kind)
        dataset = factory()
        if dataset is None:
            raise ProfileError(
                f"Profile {context.profile.id!r} enables {kind!r}, but its "
                "builder returned no dataset"
            )
        return dataset

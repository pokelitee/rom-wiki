"""Write built game datasets, comparisons, and public data downloads.

Focused section, complete single-game, and sibling-version family builds all
write through this module, so they share dataset output paths, comparison
handling, and the public `wiki/data` exports.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from romwiki.pipeline.build.sections import (
    dataset_enabled,
    describe_section_mismatch,
    enabled_dataset_kinds,
)
from romwiki.pipeline.build.workflow import GameBuildWorkflow
from romwiki.pipeline.enrichment.type_charts import build_type_dataset
from romwiki.pipeline.io import write_dataset
from romwiki.pipeline.transforms.version_merge import (
    merge_version_family_comparisons,
    merge_version_family_datasets,
)
from romwiki.sites.data_exports import (
    prune_public_datasets,
    write_public_comparison,
    write_public_dataset,
)
from romwiki.util.errors import LocalConfigError

_LOG = logging.getLogger("romwiki")

SECTION_BUILD_KINDS: dict[str, tuple[str, ...]] = {
    "pokemon": ("pokemon", "abilities"),
    "encounters": ("encounters",),
    "trainers": ("trainers",),
    "locations": ("locations",),
    "moves": ("moves",),
    "items": ("items",),
}


def dataset_output(data_root: Path, kind: str) -> Path:
    filename = "raw.json" if kind == "locations" else "enriched.json"
    return data_root / kind / filename


def write_section(
    kind: str,
    dataset: dict[str, Any],
    comparison: dict[str, Any] | None,
    data_output: Path,
    wiki_root: Path,
) -> None:
    """Write one section's dataset, comparison, and public download."""
    write_dataset(dataset, data_output, compact=True)
    if comparison is not None:
        comparison_output = data_output.parent.parent / "comparisons" / f"{kind}.json"
        write_dataset(comparison, comparison_output, sort_keys=False, compact=True)
    write_public_dataset(wiki_root, kind, dataset)
    write_public_comparison(wiki_root, kind, comparison)
    _LOG.info(
        "Wrote %s %s records: %s",
        len(dataset["records"]),
        kind,
        data_output,
    )


def write_type_section(
    dataset: dict[str, Any],
    data_root: Path,
    wiki_root: Path,
) -> None:
    data_output = dataset_output(data_root, "types")
    write_dataset(dataset, data_output, compact=True)
    write_public_dataset(wiki_root, "types", dataset)
    _LOG.info("Wrote %s types: %s", len(dataset["records"]), data_output)


def write_game_build(
    workflow: GameBuildWorkflow,
    *,
    data_root: Path,
    wiki_root: Path,
) -> None:
    """Build and write every enabled dataset for one game.

    `data_root` is the game's own data directory below the generated data root.
    """
    builds = workflow.build_all()
    _write_game(
        workflow.current.profile.id,
        {kind: build.current for kind, build in builds.items()},
        {
            kind: build.comparison
            for kind, build in builds.items()
            if build.comparison is not None
        },
        type_dataset=build_type_dataset(workflow.current.profile),
        data_root=data_root,
        wiki_root=wiki_root,
    )


def write_version_family_build(
    site_id: str,
    workflows: Mapping[str, GameBuildWorkflow],
    versions: Sequence[str],
    *,
    data_root: Path,
    wiki_root: Path,
) -> None:
    """Merge sibling versions' datasets and write them as one site.

    `data_root` is the site's own data directory below the generated data root.
    """
    if set(workflows) != set(versions):
        raise LocalConfigError(
            "Prepared version-family workflows do not match configured versions"
        )
    enabled_by_version = {
        version: enabled_dataset_kinds(workflows[version].current.profile)
        for version in versions
    }
    enabled_sets = set(enabled_by_version.values())
    if len(enabled_sets) != 1:
        raise LocalConfigError(
            "Version-family profiles enable different dataset sections: "
            f"{describe_section_mismatch(enabled_by_version)}"
        )
    kinds = next(iter(enabled_sets))

    merged_datasets: dict[str, dict[str, Any]] = {}
    merged_comparisons: dict[str, dict[str, Any]] = {}
    for kind in kinds:
        builds = {version: workflows[version].build(kind) for version in versions}
        merged_datasets[kind] = merge_version_family_datasets(
            {version: build.current for version, build in builds.items()}
        )
        comparisons = {
            version: build.comparison
            for version, build in builds.items()
            if build.comparison is not None
        }
        if comparisons:
            merged_comparisons[kind] = merge_version_family_comparisons(comparisons)

    type_datasets = [
        build_type_dataset(workflows[version].current.profile, game=site_id)
        for version in versions
    ]
    if any(
        dataset["records"] != type_datasets[0]["records"]
        for dataset in type_datasets[1:]
    ):
        raise LocalConfigError(
            "Version-family profiles must declare matching type charts"
        )
    _write_game(
        site_id,
        merged_datasets,
        merged_comparisons,
        type_dataset=type_datasets[0],
        data_root=data_root,
        wiki_root=wiki_root,
    )


def _write_game(
    game: str,
    datasets: dict[str, dict[str, Any]],
    comparisons: dict[str, dict[str, Any]],
    *,
    type_dataset: dict[str, Any],
    data_root: Path,
    wiki_root: Path,
) -> None:
    prune_public_datasets(wiki_root, {*datasets, "types"}, game)
    for path in (wiki_root / "data/comparisons").glob("*.json"):
        if path.stem not in comparisons:
            path.unlink()
    write_type_section(type_dataset, data_root, wiki_root)
    for kind, dataset in datasets.items():
        write_section(
            kind,
            dataset,
            comparisons.get(kind),
            dataset_output(data_root, kind),
            wiki_root,
        )
    comparison_root = data_root / "comparisons"
    if comparison_root.is_dir():
        for path in comparison_root.glob("*.json"):
            if path.stem not in comparisons:
                path.unlink()


def write_section_build(
    section: str,
    workflow: GameBuildWorkflow,
    *,
    data_root: Path,
    wiki_root: Path,
    data_output: Path | None = None,
) -> None:
    """Build and write one section's datasets.

    `data_output` replaces the default path of the section's primary dataset
    only; companion datasets keep their default locations.
    """
    profile = workflow.current.profile
    # An engine whose first vertical slice decodes only personal data (no
    # ability-name table yet) can still build its Pokémon section.
    kinds = tuple(
        kind
        for kind in SECTION_BUILD_KINDS[section]
        if kind != "abilities" or dataset_enabled(profile, "abilities")
    )
    if section == "pokemon":
        write_type_section(build_type_dataset(profile), data_root, wiki_root)
    for index, kind in enumerate(kinds):
        build = workflow.build(kind)
        write_section(
            kind,
            build.current,
            build.comparison,
            (
                data_output
                if index == 0 and data_output is not None
                else dataset_output(data_root, kind)
            ),
            wiki_root,
        )
        if build.comparison is None:
            comparison_path = data_root / "comparisons" / f"{kind}.json"
            if comparison_path.is_file():
                comparison_path.unlink()

"""Write built game datasets and render them into a wiki.

Focused section, complete single-game, and sibling-version family builds all
publish through this module, so they share dataset output paths, cross-section
indexes, renderer invocation, and change-overview handling.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from romwiki.pipeline.build.context import GameBuildContext
from romwiki.pipeline.build.sections import (
    dataset_enabled,
    describe_section_mismatch,
    enabled_dataset_kinds,
)
from romwiki.pipeline.build.workflow import DatasetBuild, GameBuildWorkflow
from romwiki.pipeline.enrichment.type_charts import build_type_dataset
from romwiki.pipeline.io import write_dataset
from romwiki.pipeline.transforms.relationships import (
    RelationshipIndex,
    build_relationship_index,
)
from romwiki.pipeline.transforms.version_merge import (
    merge_version_family_comparisons,
    merge_version_family_datasets,
)
from romwiki.renderers.mkdocs import (
    render_ability_pages,
    render_encounter_pages,
    render_item_pages,
    render_location_pages,
    render_move_pages,
    render_pokemon_pages,
    render_trainer_pages,
    render_type_chart,
)
from romwiki.renderers.mkdocs.comparisons import render_changes_pages
from romwiki.renderers.mkdocs.references import ReferenceIndex
from romwiki.sites.data_exports import prune_public_datasets, write_public_dataset
from romwiki.sites.dev_pages import DevPages
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


@dataclass(frozen=True, slots=True)
class RenderContext:
    """Cross-section inputs shared by every section rendered in one build."""

    reference_index: ReferenceIndex | None = None
    relationship_index: RelationshipIndex | None = None
    move_dataset: dict[str, Any] | None = None
    type_dataset: dict[str, Any] | None = None
    comparisons: Mapping[str, dict[str, Any]] = field(default_factory=dict)
    dev_pages: DevPages | None = None


_SectionRenderer = Callable[
    [dict[str, Any], Path, dict[str, Any] | None, RenderContext, frozenset[str] | None],
    int,
]


def _render_pokemon(
    dataset: Any,
    output: Path,
    comparison: dict[str, Any] | None,
    context: RenderContext,
    only_pages: frozenset[str] | None,
) -> int:
    return render_pokemon_pages(
        dataset,
        output,
        comparison,
        context.move_dataset,
        context.reference_index,
        context.relationship_index,
        context.type_dataset,
        only_pages=only_pages,
    )


def _render_abilities(
    dataset: Any,
    output: Path,
    comparison: dict[str, Any] | None,
    context: RenderContext,
    only_pages: frozenset[str] | None,
) -> int:
    return render_ability_pages(
        dataset,
        output,
        comparison,
        context.reference_index,
        only_pages=only_pages,
    )


def _render_locations(
    dataset: Any,
    output: Path,
    comparison: dict[str, Any] | None,
    context: RenderContext,
    only_pages: frozenset[str] | None,
) -> int:
    return render_location_pages(
        dataset,
        output,
        comparison,
        context.reference_index,
        context.relationship_index,
        context.comparisons.get("encounters"),
        only_pages=only_pages,
    )


def _related_section_renderer(
    renderer: Callable[..., int],
) -> _SectionRenderer:
    def render(
        dataset: Any,
        output: Path,
        comparison: dict[str, Any] | None,
        context: RenderContext,
        only_pages: frozenset[str] | None,
    ) -> int:
        return renderer(
            dataset,
            output,
            comparison,
            context.reference_index,
            context.relationship_index,
            only_pages=only_pages,
        )

    return render


# Renderer entry points take kind-specific companion inputs; these adapters give
# every section the same call shape without coupling renderers to RenderContext.
_SECTION_RENDERERS: dict[str, _SectionRenderer] = {
    "pokemon": _render_pokemon,
    "abilities": _render_abilities,
    "moves": _related_section_renderer(render_move_pages),
    "items": _related_section_renderer(render_item_pages),
    "encounters": _related_section_renderer(render_encounter_pages),
    "trainers": _related_section_renderer(render_trainer_pages),
    "locations": _render_locations,
}


def dataset_output(data_root: Path, kind: str) -> Path:
    filename = "raw.json" if kind == "locations" else "enriched.json"
    return data_root / kind / filename


def write_section(
    kind: str,
    dataset: dict[str, Any],
    comparison: dict[str, Any] | None,
    data_output: Path,
    wiki_output: Path,
    context: RenderContext,
) -> None:
    """Write one section's dataset, comparison, public download, and pages."""
    write_dataset(dataset, data_output)
    if comparison is not None:
        comparison_output = data_output.parent.parent / "comparisons" / f"{kind}.json"
        write_dataset(comparison, comparison_output)
    write_public_dataset(wiki_output.parent, kind, dataset)
    page_count = _SECTION_RENDERERS[kind](
        dataset,
        wiki_output,
        comparison,
        context,
        context.dev_pages.pages_for(kind) if context.dev_pages else None,
    )
    _LOG.info(
        "Wrote %s %s records: %s",
        len(dataset["records"]),
        kind,
        data_output,
    )
    _LOG.info("Rendered %s %s pages: %s", page_count, kind, wiki_output)


def write_type_section(
    dataset: dict[str, Any],
    data_root: Path,
    wiki_root: Path,
) -> None:
    data_output = dataset_output(data_root, "types")
    write_dataset(dataset, data_output)
    write_public_dataset(wiki_root, "types", dataset)
    page_count = render_type_chart(dataset, wiki_root / "types")
    _LOG.info("Wrote %s types: %s", len(dataset["records"]), data_output)
    _LOG.info(
        "Rendered %s type chart page: %s",
        page_count,
        wiki_root / "types",
    )


def render_game_build(
    workflow: GameBuildWorkflow,
    *,
    data_root: Path,
    wiki_root: Path,
    dev: bool = False,
) -> None:
    """Build, write, and render every enabled dataset for one game.

    `data_root` is the game's own data directory below the generated data root.
    """
    dev_pages = _dev_pages(wiki_root) if dev else None
    builds = workflow.build_all()
    trades = workflow.current.trades()
    _render_game(
        workflow.current.profile.id,
        {kind: build.current for kind, build in builds.items()},
        {
            kind: build.comparison
            for kind, build in builds.items()
            if build.comparison is not None
        },
        companions={"trades": trades} if trades is not None else {},
        type_dataset=build_type_dataset(workflow.current.profile),
        data_root=data_root,
        wiki_root=wiki_root,
        dev_pages=dev_pages,
        render_uncompared_changes=True,
    )


def render_version_family_build(
    site_id: str,
    workflows: Mapping[str, GameBuildWorkflow],
    versions: Sequence[str],
    *,
    data_root: Path,
    wiki_root: Path,
    dev: bool = False,
) -> None:
    """Merge sibling versions' datasets and render them as one site.

    `data_root` is the site's own data directory below the generated data root.
    """
    if set(workflows) != set(versions):
        raise LocalConfigError(
            "Prepared version-family workflows do not match configured versions"
        )
    dev_pages = _dev_pages(wiki_root) if dev else None
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

    trade_datasets = {
        version: trade
        for version, workflow in workflows.items()
        if (trade := workflow.current.trades()) is not None
    }
    companions: dict[str, dict[str, Any]] = {}
    if trade_datasets:
        if len(trade_datasets) != len(workflows):
            raise LocalConfigError(
                "Version-family games must have matching trade capabilities"
            )
        companions["trades"] = merge_version_family_datasets(trade_datasets)

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
    _render_game(
        site_id,
        merged_datasets,
        merged_comparisons,
        companions=companions,
        type_dataset=type_datasets[0],
        data_root=data_root,
        wiki_root=wiki_root,
        dev_pages=dev_pages,
        render_uncompared_changes=False,
    )


def _render_game(
    game: str,
    datasets: dict[str, dict[str, Any]],
    comparisons: dict[str, dict[str, Any]],
    *,
    companions: Mapping[str, dict[str, Any]],
    type_dataset: dict[str, Any],
    data_root: Path,
    wiki_root: Path,
    dev_pages: DevPages | None,
    render_uncompared_changes: bool,
) -> None:
    context = RenderContext(
        reference_index=ReferenceIndex.from_datasets(datasets),
        relationship_index=build_relationship_index({**datasets, **companions}),
        move_dataset=datasets.get("moves"),
        type_dataset=type_dataset,
        comparisons=comparisons,
        dev_pages=dev_pages,
    )
    prune_public_datasets(wiki_root, {*datasets, "types"}, game)
    write_type_section(type_dataset, data_root, wiki_root)
    for kind, dataset in datasets.items():
        write_section(
            kind,
            dataset,
            comparisons.get(kind),
            dataset_output(data_root, kind),
            wiki_root / kind,
            context,
        )
    if not comparisons:
        comparison_root = data_root / "comparisons"
        if comparison_root.is_dir():
            for path in comparison_root.glob("*.json"):
                path.unlink()
        # Single games publish an explicit "no comparison" overview; merged
        # version families omit the Changes section entirely.
        if not render_uncompared_changes:
            return
    page_count = render_changes_pages(
        comparisons, wiki_root, context.relationship_index
    )
    _LOG.info(
        "Rendered %s change overview pages: %s",
        page_count,
        wiki_root / "changes",
    )


def render_section_build(
    section: str,
    workflow: GameBuildWorkflow,
    *,
    data_root: Path,
    wiki_root: Path,
    data_output: Path | None = None,
    wiki_output: Path | None = None,
    dev: bool = False,
) -> None:
    """Build and render one wiki section plus the companions it links to.

    `data_output` and `wiki_output` replace the default paths of the section's
    primary dataset only; companion datasets keep their default locations.
    """
    profile = workflow.current.profile
    move_dataset = None
    # Cross-linking Pokémon/Ability pages to move names is a nice-to-have, not
    # a requirement: an engine that hasn't implemented moves yet (e.g. a new
    # generation's first vertical slice) should still be able to build its
    # Pokémon section. Gated declaratively on the profile, matching
    # GameBuildContext's optional-input accessors, rather than probing with a
    # try/except around the build.
    if section == "pokemon" and "moves" in profile.layout:
        move_dataset = workflow.build("moves").current
    dev_pages = _dev_pages(wiki_root) if dev else None
    comparisons = load_comparisons(data_root / "comparisons")
    # An engine's Abilities section needs ROM-decoded ability names with no
    # PokéDB fallback (unlike Pokémon page names); an engine whose first
    # vertical slice implements only personal data (no ability-name table
    # decoding yet) can still build its Pokémon section without one. Gated
    # declaratively via `dataset_enabled`, the same "personal_offset or
    # personal layout, per platform" check `pipeline/build/context.py`'s
    # `items_raw`/`trainers_raw` accessors already use -- checking for a
    # `"messages"` layout entry specifically would only ever be true for
    # NDS/archive-shaped profiles, never for flat-offset (GBA) ones.
    abilities_build = None
    if section == "pokemon" and dataset_enabled(profile, "abilities"):
        abilities_build = workflow.build("abilities")
    relationship_index = None
    type_dataset = None
    relationship_datasets: dict[str, dict[str, Any]] = {}
    if section == "pokemon":
        relationship_datasets = current_relationship_datasets(workflow.current)
        relationship_index = build_relationship_index(relationship_datasets)
        type_dataset = build_type_dataset(profile)
        write_type_section(type_dataset, data_root, wiki_root)
    elif section == "moves":
        relationship_datasets = {"pokemon": workflow.current.pokemon()}
        relationship_index = build_relationship_index(relationship_datasets)
    elif section == "encounters":
        relationship_datasets = {"encounters": workflow.current.encounters()}
        locations = workflow.current.locations()
        if locations is not None:
            relationship_datasets["locations"] = locations
        relationship_index = build_relationship_index(relationship_datasets)
    elif section in {"items", "trainers"}:
        locations = workflow.current.locations()
        if locations is not None:
            relationship_datasets = {"locations": locations}
            relationship_index = build_relationship_index(relationship_datasets)
    reference_datasets = {}
    if section == "locations":
        current_locations = workflow.current.locations()
        if current_locations is None:
            raise LocalConfigError(
                "The build-locations command requires a profile with a "
                "locations dataset"
            )
        relationship_datasets = {
            "locations": current_locations,
            "encounters": workflow.current.encounters(),
        }
        relationship_index = build_relationship_index(relationship_datasets)
        reference_datasets = {
            "pokemon": workflow.current.pokemon(),
            "items": workflow.current.items(),
        }
    elif section == "pokemon":
        reference_datasets = dict(relationship_datasets)
        if abilities_build is not None:
            reference_datasets["abilities"] = abilities_build.current
        if move_dataset is not None:
            reference_datasets["moves"] = move_dataset
    elif section == "moves":
        reference_datasets = dict(relationship_datasets)
    elif section in {"encounters", "items", "trainers"}:
        reference_datasets = {"pokemon": workflow.current.pokemon()}
    context = RenderContext(
        reference_index=(
            ReferenceIndex.from_datasets(reference_datasets)
            if reference_datasets
            else None
        ),
        relationship_index=relationship_index,
        move_dataset=move_dataset,
        type_dataset=type_dataset,
        comparisons=comparisons,
        dev_pages=dev_pages,
    )
    kinds = tuple(
        kind
        for kind in SECTION_BUILD_KINDS[section]
        if kind != "abilities" or abilities_build is not None
    )
    for index, kind in enumerate(kinds):
        build: DatasetBuild = (
            abilities_build
            if kind == "abilities" and abilities_build is not None
            else workflow.build(kind)
        )
        write_section(
            kind,
            build.current,
            build.comparison,
            (
                data_output
                if index == 0 and data_output is not None
                else dataset_output(data_root, kind)
            ),
            (
                wiki_output
                if index == 0 and wiki_output is not None
                else wiki_root / kind
            ),
            context,
        )
        if build.comparison is not None:
            comparisons[kind] = build.comparison
        else:
            comparisons.pop(kind, None)
            comparison_path = data_root / "comparisons" / f"{kind}.json"
            if comparison_path.is_file():
                comparison_path.unlink()
    render_changes_pages(comparisons, wiki_root, relationship_index)


def current_relationship_datasets(
    context: GameBuildContext,
) -> dict[str, dict[str, Any]]:
    # "trades" has no dedicated dataset_kind (it's an optional per-engine
    # detail, always None-safe) so it's never gated here; the rest correspond
    # 1:1 to a DATASET_KINDS entry and are only built when the profile's
    # engine actually declares support for it -- a personal-data-only
    # vertical slice (an engine's first onboarding step, per
    # adding-a-game.md) has nothing to build for the others yet.
    enabled = set(enabled_dataset_kinds(context.profile))
    accessors: dict[str, tuple[str | None, Callable[[], dict[str, Any] | None]]] = {
        "pokemon": ("pokemon", context.pokemon),
        "encounters": ("encounters", context.encounters),
        "trainers": ("trainers", context.trainers),
        "locations": ("locations", context.locations),
        "items": ("items", context.items),
        "trades": (None, context.trades),
    }
    datasets = {
        name: accessor()
        for name, (kind, accessor) in accessors.items()
        if kind is None or kind in enabled
    }
    return {kind: dataset for kind, dataset in datasets.items() if dataset is not None}


def load_comparisons(root: Path) -> dict[str, dict[str, Any]]:
    """Load comparisons written by earlier builds, keyed by workflow kind."""
    comparisons: dict[str, dict[str, Any]] = {}
    if not root.is_dir():
        return comparisons
    for path in root.glob("*.json"):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(value, dict) and isinstance(value.get("kind"), str):
            comparisons[comparison_workflow_kind(value["kind"])] = value
    return comparisons


def comparison_workflow_kind(kind: str) -> str:
    return "encounters" if kind == "wild_encounters" else kind


def _dev_pages(wiki_root: Path) -> DevPages:
    return DevPages.load(wiki_root.parent / "dev-pages.toml")

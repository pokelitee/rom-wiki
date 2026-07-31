from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from time import perf_counter

from romwiki.engines.registry import get_engine
from romwiki.pipeline.build_context import GameBuildContext
from romwiki.pipeline.comparisons import write_comparison_dataset
from romwiki.pipeline.egg_moves import (
    extract_egg_move_dataset,
    write_egg_move_dataset,
)
from romwiki.pipeline.encounters import (
    extract_encounter_dataset,
    write_encounter_dataset,
)
from romwiki.pipeline.enrich import (
    write_enriched_dataset,
)
from romwiki.pipeline.evolutions import (
    extract_evolution_dataset,
    write_evolution_dataset,
)
from romwiki.pipeline.game_build import DATASET_KINDS, GameBuildWorkflow
from romwiki.pipeline.identify import InspectionResult, inspect_rom
from romwiki.pipeline.items import (
    extract_item_dataset,
    write_item_dataset,
)
from romwiki.pipeline.learnsets import extract_learnset_dataset, write_learnset_dataset
from romwiki.pipeline.locations import extract_location_dataset, write_location_dataset
from romwiki.pipeline.machines import extract_machine_dataset, write_machine_dataset
from romwiki.pipeline.manifest import create_manifest, write_manifest
from romwiki.pipeline.marts import extract_mart_dataset
from romwiki.pipeline.moves import extract_move_dataset, write_move_dataset
from romwiki.pipeline.personal import extract_personal_dataset, write_personal_dataset
from romwiki.pipeline.pickup import extract_pickup_dataset, write_pickup_dataset
from romwiki.pipeline.relationships import (
    RelationshipIndex,
    build_relationship_index,
)
from romwiki.pipeline.static_encounters import extract_static_encounter_dataset
from romwiki.pipeline.trainers import extract_trainer_dataset, write_trainer_dataset
from romwiki.pipeline.tutors import extract_tutor_dataset, write_tutor_dataset
from romwiki.pipeline.type_charts import build_type_dataset
from romwiki.pipeline.version_merge import (
    merge_version_family_comparisons,
    merge_version_family_datasets,
)
from romwiki.profiles.loader import ProfileRepository
from romwiki.profiles.models import GameProfile
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
from romwiki.sites import (
    SiteAuditReport,
    SiteCatalog,
    SiteDefinition,
    audit_site,
    build_sites,
    create_generated_wiki_snapshot,
    restore_generated_wiki_snapshot,
    serve_sites,
)
from romwiki.sites.data_exports import write_public_dataset
from romwiki.sites.dev_pages import DevPages
from romwiki.sources import PokeDBGeneration
from romwiki.util.errors import (
    LocalConfigError,
    RomWikiError,
    SiteError,
)
from romwiki.util.local_config import LocalGamePaths, LocalGameRegistry
from romwiki.util.logging import configure_logging, timed_operation

_LOG = logging.getLogger("romwiki")
_LEGACY_COMMANDS = {
    "manifest": ("inspect", "--manifest-output"),
    "extract-personal": ("extract", "personal"),
    "extract-encounters": ("extract", "encounters"),
    "extract-trainers": ("extract", "trainers"),
    "extract-locations": ("extract", "locations"),
    "extract-moves": ("extract", "moves"),
    "extract-items": ("extract", "items"),
    "extract-learnsets": ("extract", "learnsets"),
    "extract-egg-moves": ("extract", "egg-moves"),
    "extract-evolutions": ("extract", "evolutions"),
    "extract-machines": ("extract", "machines"),
    "extract-tutors": ("extract", "tutors"),
    "extract-pickup": ("extract", "pickup"),
    "build-pokemon": ("build", "pokemon"),
    "build-encounters": ("build", "encounters"),
    "build-trainers": ("build", "trainers"),
    "build-locations": ("build", "locations"),
    "build-moves": ("build", "moves"),
    "build-items": ("build", "items"),
    "build-game": ("build", "game"),
    "build-version-family": ("build", "family"),
    "build-version-pair": ("build", "family"),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="romwiki",
        description="Extract structured Pokémon ROM data for static wikis.",
    )
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="show detailed diagnostic output",
    )
    output_group.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="show warnings and errors only",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="identify a ROM image")
    _add_input_arguments(inspect_parser)
    inspect_parser.add_argument("--json", action="store_true", help="emit JSON")
    inspect_parser.add_argument(
        "--manifest-output",
        type=Path,
        help="write a versioned input manifest to this path",
    )

    extract_parser = subparsers.add_parser(
        "extract", help="write one normalized single-ROM audit dataset"
    )
    extract_subparsers = extract_parser.add_subparsers(
        dest="extract_kind", required=True
    )

    extract_specs = (
        ("personal", "extract normalized Pokémon personal data", "pokemon"),
        ("encounters", "extract normalized wild encounter data", "encounters"),
        ("trainers", "extract normalized trainer and party data", "trainers"),
        ("locations", "extract normalized map locations and navigation", "locations"),
        ("moves", "extract normalized move mechanics", "moves"),
        ("items", "extract normalized item mechanics", "items"),
        ("learnsets", "extract normalized level-up learnsets", "pokemon"),
        ("egg-moves", "extract normalized Pokémon egg moves", "pokemon"),
        ("evolutions", "extract normalized Pokémon evolutions", "pokemon"),
        ("machines", "extract TM/HM move assignments", "machines"),
        ("tutors", "extract move tutor assignments and compatibility", "tutors"),
        ("pickup", "extract Pickup/Honey Gather item and rate tables", "pickup"),
    )
    for kind, help_text, output_group in extract_specs:
        extract_kind_parser = extract_subparsers.add_parser(kind, help=help_text)
        _add_input_arguments(extract_kind_parser)
        extract_kind_parser.add_argument(
            "--output",
            type=Path,
            help=(
                "dataset output path "
                f"(default: below build/data/<profile>/{output_group})"
            ),
        )

    build_group_parser = subparsers.add_parser(
        "build", help="build one section, game, or sibling-version family"
    )
    build_subparsers = build_group_parser.add_subparsers(
        dest="build_command", required=True
    )

    build_specs = (
        ("pokemon", "extract, enrich, and render Pokémon pages", "enriched"),
        (
            "encounters",
            "extract, enrich, and render wild encounter pages",
            "enriched",
        ),
        ("trainers", "extract, enrich, and render trainer pages", "enriched"),
        ("locations", "extract and render location navigation pages", "normalized"),
        ("moves", "extract, enrich, and render move pages", "enriched"),
        ("items", "extract, enrich, and render item pages", "enriched"),
    )
    for kind, help_text, data_label in build_specs:
        section_parser = build_subparsers.add_parser(kind, help=help_text)
        _add_input_arguments(section_parser)
        section_parser.add_argument(
            "--pokedb",
            type=Path,
            help=(
                "PokéDB generation output directory "
                "(default: derived from the ROM profile)"
            ),
        )
        section_parser.add_argument(
            "--data-output",
            type=Path,
            help=f"{data_label} dataset JSON output file",
        )
        section_parser.add_argument(
            "--wiki-output",
            type=Path,
            help="generated section directory",
        )
        _add_comparison_arguments(section_parser)
        _add_dev_argument(section_parser)
        _add_cache_argument(section_parser)

    build_game_parser = build_subparsers.add_parser(
        "game", help="build every dataset and wiki section for one game"
    )
    _add_input_arguments(build_game_parser)
    _add_comparison_arguments(build_game_parser)
    _add_dev_argument(build_game_parser)
    _add_cache_argument(build_game_parser)
    build_game_parser.add_argument(
        "--pokedb",
        type=Path,
        help="PokéDB generation output directory (default: derived from the ROM profile)",
    )
    build_game_parser.add_argument(
        "--data-root",
        type=Path,
        default=Path("build/data"),
        help="generated data root (default: build/data)",
    )
    build_game_parser.add_argument(
        "--wiki-root",
        type=Path,
        help="game wiki root (default: site catalog entry for the matched profile)",
    )

    family_parser = build_subparsers.add_parser(
        "family",
        help="build one merged wiki for a sibling game-version family",
    )
    family_parser.add_argument(
        "--games",
        nargs="+",
        metavar="GAME",
        required=True,
        help="two or more game identifiers from the local game configuration",
    )
    family_parser.add_argument(
        "--versions",
        nargs="+",
        metavar="LABEL",
        help="version labels used for tagging records (default: the --games values)",
    )
    family_parser.add_argument(
        "--site-id",
        required=True,
        help=("merged site identifier used for data and wiki output"),
    )
    family_parser.add_argument(
        "--games-config", type=Path, default=Path(".local/games.toml")
    )
    family_parser.add_argument("--profiles-dir", type=Path, default=Path("profiles"))
    family_parser.add_argument(
        "--pokedb",
        type=Path,
        help="PokéDB generation output directory (default: derived from the ROM profiles)",
    )
    family_parser.add_argument(
        "--data-root",
        type=Path,
        default=Path("build/data"),
        help="generated data root (default: build/data)",
    )
    family_parser.add_argument(
        "--wiki-root",
        type=Path,
        help="merged game wiki root (default: resolved from --site-id)",
    )
    family_parser.add_argument(
        "--refresh-baseline",
        action="store_true",
        help="ignore and replace cached clean-ROM extraction data",
    )
    _add_dev_argument(family_parser)
    _add_cache_argument(family_parser)

    regenerate_parser = subparsers.add_parser(
        "regenerate",
        help="regenerate selected game data, build sites, and audit the artifact",
    )
    regenerate_parser.add_argument("site_ids", nargs="*", help="game site identifiers")
    regenerate_parser.add_argument(
        "--all",
        action="store_true",
        dest="regenerate_all",
        help="regenerate every published data-driven game and build all sites",
    )
    regenerate_parser.add_argument(
        "--games-config", type=Path, default=Path(".local/games.toml")
    )
    regenerate_parser.add_argument(
        "--profiles-dir", type=Path, default=Path("profiles")
    )
    regenerate_parser.add_argument(
        "--pokedb-root",
        type=Path,
        default=Path("../pokedb/.output"),
        help="directory containing gen<N> PokéDB outputs",
    )
    regenerate_parser.add_argument("--data-root", type=Path, default=Path("build/data"))
    regenerate_parser.add_argument(
        "--output", type=Path, default=Path("dist"), help="artifact output directory"
    )
    regenerate_parser.add_argument(
        "--refresh",
        action="store_true",
        help="replace current-ROM and clean-baseline extraction caches",
    )
    regenerate_parser.add_argument(
        "--snapshot",
        action="store_true",
        help="update the generated-wiki snapshot after a successful audit",
    )
    regenerate_parser.add_argument(
        "--snapshot-output",
        type=Path,
        default=Path("sites/generated-wiki.tar.gz"),
    )
    regenerate_parser.add_argument("--max-page-kb", type=int, default=512)
    regenerate_parser.add_argument("--max-images", type=int, default=150)
    regenerate_parser.add_argument("--base-url")
    _add_site_root_argument(regenerate_parser)

    baseline_parser = subparsers.add_parser(
        "baseline", help="manage clean-ROM baseline caches"
    )
    baseline_subparsers = baseline_parser.add_subparsers(
        dest="baseline_command", required=True
    )
    baseline_build_parser = baseline_subparsers.add_parser(
        "build", help="extract and cache a configured clean base ROM"
    )
    baseline_build_parser.add_argument("--game", required=True)
    baseline_build_parser.add_argument(
        "--games-config", type=Path, default=Path(".local/games.toml")
    )
    baseline_build_parser.add_argument(
        "--profiles-dir", type=Path, default=Path("profiles")
    )
    baseline_build_parser.add_argument(
        "--pokedb",
        type=Path,
        help="PokéDB generation output directory (default: derived from the ROM profile)",
    )
    baseline_build_parser.add_argument(
        "--data-root",
        type=Path,
        default=Path("build/data"),
        help="generated data root (default: build/data)",
    )
    baseline_build_parser.add_argument(
        "--scope", nargs="+", choices=DATASET_KINDS, default=list(DATASET_KINDS)
    )
    baseline_build_parser.add_argument("--refresh", action="store_true")

    site_parser = subparsers.add_parser(
        "site", help="list, build, serve, audit, snapshot, and restore wiki sites"
    )
    site_subparsers = site_parser.add_subparsers(dest="site_command", required=True)
    list_parser = site_subparsers.add_parser("list", help="list configured sites")
    list_parser.add_argument(
        "--json",
        action="store_true",
        help="emit compact machine-readable site metadata",
    )
    list_parser.add_argument(
        "--published",
        action="store_true",
        help="list published sites only",
    )
    _add_site_root_argument(list_parser)

    build_site_parser = site_subparsers.add_parser(
        "build", help="build selected MkDocs sites into one Pages artifact"
    )
    build_site_parser.add_argument("site_ids", nargs="*", help="site identifiers")
    build_site_parser.add_argument(
        "--all", action="store_true", dest="build_all", help="build published sites"
    )
    build_site_parser.add_argument(
        "--output", type=Path, default=Path("dist"), help="artifact output directory"
    )
    _add_site_root_argument(build_site_parser)
    serve_site_parser = site_subparsers.add_parser(
        "serve",
        help="build, serve, and live-reload selected wiki sites",
    )
    serve_site_parser.add_argument("site_ids", nargs="*", help="site identifiers")
    serve_site_parser.add_argument(
        "--all",
        action="store_true",
        dest="serve_all",
        help="serve all published sites",
    )
    serve_site_parser.add_argument(
        "--dev",
        action="store_true",
        help="use lightweight development MkDocs configurations",
    )
    serve_site_parser.add_argument(
        "--output",
        type=Path,
        default=Path("build/mkdocs-dev"),
        help="served artifact directory",
    )
    serve_site_parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="interface to bind (default: 127.0.0.1)",
    )
    serve_site_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="port to bind (default: 8000)",
    )
    _add_site_root_argument(serve_site_parser)
    audit_site_parser = site_subparsers.add_parser(
        "audit", help="validate a rendered multi-site artifact"
    )
    audit_site_parser.add_argument("artifact", type=Path)
    audit_site_parser.add_argument(
        "--max-page-kb",
        type=int,
        default=512,
        help="maximum rendered HTML page size in KiB (default: 512)",
    )
    audit_site_parser.add_argument(
        "--max-images",
        type=int,
        default=150,
        help="image count that triggers a warning on one page (default: 150)",
    )
    audit_site_parser.add_argument(
        "--base-url",
        help="deployment base URL used to resolve absolute project-site links",
    )
    snapshot_parser = site_subparsers.add_parser(
        "snapshot", help="archive generated, ROM-free wiki Markdown"
    )
    snapshot_parser.add_argument(
        "--output",
        type=Path,
        default=Path("sites/generated-wiki.tar.gz"),
    )
    _add_site_root_argument(snapshot_parser)
    restore_parser = site_subparsers.add_parser(
        "restore-snapshot", help="restore generated wiki Markdown"
    )
    restore_parser.add_argument(
        "archive",
        type=Path,
        nargs="?",
        default=Path("sites/generated-wiki.tar.gz"),
    )
    _add_site_root_argument(restore_parser)
    return parser


def _normalize_legacy_argv(
    argv: Sequence[str],
) -> tuple[tuple[str, ...], str | None]:
    values = list(argv)
    command_index = next(
        (
            index
            for index, value in enumerate(values)
            if value not in {"-v", "--verbose", "-q", "--quiet"}
        ),
        None,
    )
    if command_index is None:
        return tuple(values), None
    command = values[command_index]
    if command == "manifest":
        values[command_index] = "inspect"
        if "--output" in values:
            values = [
                "--manifest-output" if value == "--output" else value
                for value in values
            ]
        else:
            values.extend(("--manifest-output", "build/data/manifest.json"))
        return tuple(values), command
    replacement = _LEGACY_COMMANDS.get(command)
    if replacement is None:
        return tuple(values), None
    values[command_index : command_index + 1] = replacement
    return tuple(values), command


def main(argv: Sequence[str] | None = None) -> int:
    raw_argv = tuple(sys.argv[1:] if argv is None else argv)
    normalized_argv, legacy_command = _normalize_legacy_argv(raw_argv)
    args = build_parser().parse_args(normalized_argv)
    configure_logging(verbose=args.verbose, quiet=args.quiet)
    if legacy_command is not None:
        _LOG.warning(
            "Command %s is deprecated; use %s",
            legacy_command,
            " ".join(_LEGACY_COMMANDS.get(legacy_command, ("inspect",))),
        )
    if args.command == "extract":
        args.command = f"extract-{args.extract_kind}"
    elif args.command == "build":
        args.command = (
            "build-version-family"
            if args.build_command == "family"
            else f"build-{args.build_command}"
        )
    try:
        # Every subcommand that needs a `result` below registers ROM input
        # arguments via `_add_input_arguments`; keying off that attribute
        # (rather than a hand-maintained command list) keeps this check in
        # sync with the parser definitions by construction.
        if hasattr(args, "rom_override"):
            result = inspect_rom(_resolve_input_rom(args), args.profiles_dir)
        if args.command == "inspect":
            if args.manifest_output is not None:
                write_manifest(create_manifest(result), args.manifest_output)
                print(f"Wrote manifest: {args.manifest_output}")
            if args.manifest_output is None or args.json:
                _print_inspection(result, as_json=args.json)
        elif args.command == "extract-personal":
            dataset = extract_personal_dataset(result)
            output = args.output or (
                Path("build/data") / dataset["game"] / "pokemon" / "personal.json"
            )
            write_personal_dataset(dataset, output)
            print(f"Wrote {dataset['record_count']} personal records: {output}")
        elif args.command == "extract-encounters":
            dataset = extract_encounter_dataset(result)
            output = args.output or (
                Path("build/data") / dataset["game"] / "encounters" / "raw.json"
            )
            write_encounter_dataset(dataset, output)
            print(f"Wrote {dataset['record_count']} encounter records: {output}")
        elif args.command == "extract-trainers":
            dataset = extract_trainer_dataset(result)
            output = args.output or (
                Path("build/data") / dataset["game"] / "trainers" / "raw.json"
            )
            write_trainer_dataset(dataset, output)
            print(f"Wrote {dataset['record_count']} trainer records: {output}")
        elif args.command == "extract-locations":
            profile = result.match.profile
            dataset = extract_location_dataset(
                result,
                trainer_dataset=(
                    extract_trainer_dataset(result)
                    if "trainer_data" in profile.layout
                    else None
                ),
                static_encounter_dataset=(
                    extract_static_encounter_dataset(result)
                    if get_engine(profile.engine).formats.static_encounters != "none"
                    else None
                ),
                item_dataset=extract_item_dataset(result),
                mart_dataset=(
                    extract_mart_dataset(result)
                    if "shop_item_overlay_id" in profile.parameters
                    or "shop_items" in profile.layout
                    else None
                ),
            )
            output = args.output or (
                Path("build/data") / dataset["game"] / "locations" / "raw.json"
            )
            write_location_dataset(dataset, output)
            print(f"Wrote {dataset['record_count']} location records: {output}")
        elif args.command == "extract-moves":
            dataset = extract_move_dataset(result)
            output = args.output or (
                Path("build/data") / dataset["game"] / "moves" / "raw.json"
            )
            write_move_dataset(dataset, output)
            print(f"Wrote {dataset['record_count']} move records: {output}")
        elif args.command == "extract-items":
            dataset = extract_item_dataset(result)
            output = args.output or (
                Path("build/data") / dataset["game"] / "items" / "raw.json"
            )
            write_item_dataset(dataset, output)
            print(f"Wrote {dataset['record_count']} item records: {output}")
        elif args.command == "extract-learnsets":
            dataset = extract_learnset_dataset(result)
            output = args.output or (
                Path("build/data") / dataset["game"] / "pokemon" / "learnsets.json"
            )
            write_learnset_dataset(dataset, output)
            print(f"Wrote {dataset['record_count']} learnsets: {output}")
        elif args.command == "extract-egg-moves":
            dataset = extract_egg_move_dataset(result)
            output = args.output or (
                Path("build/data") / dataset["game"] / "pokemon" / "egg-moves.json"
            )
            write_egg_move_dataset(dataset, output)
            print(
                f"Wrote {dataset['record_count']} egg move sets with "
                f"{dataset['move_reference_count']} move references: {output}"
            )
        elif args.command == "extract-evolutions":
            dataset = extract_evolution_dataset(result)
            output = args.output or (
                Path("build/data") / dataset["game"] / "pokemon" / "evolutions.json"
            )
            write_evolution_dataset(dataset, output)
            print(f"Wrote {dataset['record_count']} evolution records: {output}")
        elif args.command == "extract-machines":
            dataset = extract_machine_dataset(result)
            output = args.output or (
                Path("build/data") / dataset["game"] / "machines" / "raw.json"
            )
            write_machine_dataset(dataset, output)
            print(f"Wrote {dataset['record_count']} machine records: {output}")
        elif args.command == "extract-tutors":
            dataset = extract_tutor_dataset(result)
            output = args.output or (
                Path("build/data") / dataset["game"] / "tutors" / "raw.json"
            )
            write_tutor_dataset(dataset, output)
            print(
                f"Wrote {dataset['record_count']} shard tutor records, "
                f"{dataset['special_record_count']} special tutor records, and "
                f"{dataset['compatibility_record_count']} shard compatibility "
                f"rows plus {dataset['special_compatibility_record_count']} "
                f"special compatibility rows: "
                f"{output}"
            )
        elif args.command == "extract-pickup":
            dataset = extract_pickup_dataset(result)
            output = args.output or (
                Path("build/data") / dataset["game"] / "pickup" / "raw.json"
            )
            write_pickup_dataset(dataset, output)
            if "level_ranges" in dataset:
                slot_count = sum(
                    len(level_range["slots"]) for level_range in dataset["level_ranges"]
                )
                print(
                    f"Wrote {len(dataset['level_ranges'])} Pickup level ranges "
                    f"with {slot_count} slots: {output}"
                )
            else:
                tables = dataset["tables"]
                print(
                    f"Wrote {len(tables['common_items'])} common and "
                    f"{len(tables['rare_items'])} rare Pickup items: {output}"
                )
        elif args.command in {
            "build-pokemon",
            "build-encounters",
            "build-trainers",
            "build-locations",
            "build-moves",
            "build-items",
        }:
            _run_section_build(args, result)
        elif args.command == "build-game":
            _run_full_game_build(args, result)
        elif args.command == "build-version-family":
            _run_version_family_build(args)
        elif args.command == "regenerate":
            _run_regeneration(args)
        elif args.command == "baseline":
            _run_baseline_build(args)
        elif args.command == "site":
            if args.site_command == "audit":
                with timed_operation(_LOG, "Site audit"):
                    report = audit_site(
                        args.artifact,
                        max_html_bytes=args.max_page_kb * 1024,
                        max_images_per_page=args.max_images,
                        base_url=args.base_url,
                    )
                _report_site_audit(report)
            elif args.site_command == "list":
                catalog = SiteCatalog.load(args.root)
                _print_sites(
                    catalog,
                    as_json=args.json,
                    published_only=args.published,
                )
            elif args.site_command == "build":
                catalog = SiteCatalog.load(args.root)
                with timed_operation(_LOG, "Site builds"):
                    built = build_sites(
                        catalog,
                        args.output,
                        site_ids=args.site_ids,
                        build_all=args.build_all,
                    )
                for site in built:
                    _LOG.info(
                        "Built %s: %s",
                        site.id,
                        site.output_path(args.output.resolve()),
                    )
            elif args.site_command == "serve":
                catalog = SiteCatalog.load(args.root)
                serve_sites(
                    catalog,
                    args.output,
                    site_ids=args.site_ids,
                    serve_all=args.serve_all,
                    dev=args.dev,
                    host=args.host,
                    port=args.port,
                )
            elif args.site_command == "snapshot":
                with timed_operation(_LOG, "Generated wiki snapshot"):
                    count = create_generated_wiki_snapshot(args.root, args.output)
                _LOG.info(
                    "Archived %s generated wiki files: %s",
                    f"{count:,}",
                    args.output,
                )
            elif args.site_command == "restore-snapshot":
                with timed_operation(_LOG, "Generated wiki snapshot restore"):
                    count = restore_generated_wiki_snapshot(args.root, args.archive)
                _LOG.info(
                    "Restored %s generated wiki files: %s",
                    f"{count:,}",
                    args.archive,
                )
        return 0
    except RomWikiError as error:
        _LOG.error("%s", error)
        return 2


def _add_input_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "input_rom",
        type=Path,
        nargs="?",
        help="path to a locally supplied ROM image (legacy positional form)",
    )
    parser.add_argument(
        "--rom",
        dest="rom_override",
        type=Path,
        help="explicit ROM path; overrides the selected local game path",
    )
    parser.add_argument(
        "--game",
        help="game identifier from the local game configuration",
    )
    parser.add_argument(
        "--base",
        action="store_true",
        help="use the selected game's clean base ROM instead of its patched ROM",
    )
    parser.add_argument(
        "--games-config",
        type=Path,
        default=Path(".local/games.toml"),
        help="local game-path configuration (default: .local/games.toml)",
    )
    parser.add_argument(
        "--profiles-dir",
        type=Path,
        default=Path("profiles"),
        help="directory containing game and hack profiles",
    )


def _add_comparison_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--base-rom",
        type=Path,
        help="clean base ROM used for exact game-data comparisons",
    )
    parser.add_argument(
        "--hack-only",
        action="store_true",
        help="build without a clean-ROM baseline or change annotations",
    )
    parser.add_argument(
        "--refresh-baseline",
        action="store_true",
        help="ignore and replace cached clean-ROM extraction data",
    )


def _add_dev_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--dev",
        action="store_true",
        help=(
            "only render the representative detail pages in the game's "
            "dev-pages.toml, keeping full catalog data; speeds up local "
            "iteration on renderer changes"
        ),
    )


def _add_cache_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--refresh-cache",
        action="store_true",
        help=(
            "ignore and replace cached raw extraction data for the current "
            "ROM; normally unnecessary since the cache already invalidates "
            "itself whenever the ROM's hash changes"
        ),
    )


def _create_build_workflow(
    args: argparse.Namespace,
    result: InspectionResult,
) -> GameBuildWorkflow:
    if result.match is None:
        raise LocalConfigError("The ROM did not match a game profile")
    pokedb = PokeDBGeneration.load(
        _resolve_pokedb_path(args.pokedb, (result.match.profile,))
    )
    baseline_path = _resolve_build_baseline(args)
    baseline = (
        inspect_rom(baseline_path, args.profiles_dir)
        if baseline_path is not None
        else None
    )
    data_root = getattr(args, "data_root", Path("build/data"))
    return GameBuildWorkflow(
        result,
        pokedb,
        baseline=baseline,
        baseline_cache_root=data_root / "baselines",
        refresh_baseline=args.refresh_baseline,
        current_cache_root=data_root / "cache",
        refresh_current=args.refresh_cache,
    )


def _resolve_build_baseline(args: argparse.Namespace) -> Path | None:
    if args.hack_only or args.base:
        if args.base_rom is not None:
            raise LocalConfigError(
                "--base-rom cannot be combined with --hack-only or --base"
            )
        return None
    if args.base_rom is not None:
        resolved = args.base_rom.resolve()
        if not resolved.is_file():
            raise LocalConfigError(f"Base ROM image does not exist: {resolved}")
        return resolved
    if args.input_rom is not None or args.rom_override is not None:
        raise LocalConfigError(
            "Explicit ROM builds require --base-rom, or --hack-only to skip comparison"
        )
    if not args.game:
        raise LocalConfigError(
            "Comparative builds require --game or --base-rom; use --hack-only to opt out"
        )
    paths = LocalGameRegistry.load(args.games_config).get(args.game)
    return paths.base_rom


def _run_section_build(args: argparse.Namespace, result: InspectionResult) -> None:
    kinds = {
        "build-pokemon": ("pokemon", "abilities"),
        "build-encounters": ("encounters",),
        "build-trainers": ("trainers",),
        "build-locations": ("locations",),
        "build-moves": ("moves",),
        "build-items": ("items",),
    }[args.command]
    workflow = _create_build_workflow(args, result)
    move_dataset = None
    # Cross-linking Pokémon/Ability pages to move names is a nice-to-have, not
    # a requirement: an engine that hasn't implemented moves yet (e.g. a new
    # generation's first vertical slice) should still be able to build its
    # Pokémon section. Gated declaratively on the profile, matching
    # GameBuildContext's optional-input accessors, rather than probing with a
    # try/except around the build.
    if args.command == "build-pokemon" and "moves" in workflow.current.profile.layout:
        move_dataset = workflow.build("moves").current
    game = workflow.current.profile.id
    wiki_root = (
        args.wiki_output.parent
        if args.wiki_output is not None
        else _profile_wiki_root(game)
    )
    dev_pages = DevPages.load(wiki_root.parent / "dev-pages.toml") if args.dev else None
    data_root = (
        args.data_output.parent.parent
        if args.data_output is not None
        else Path("build/data") / game
    )
    comparisons = _load_comparisons(data_root / "comparisons")
    # An engine's Abilities section needs ROM-decoded ability names with no
    # PokéDB fallback (unlike Pokémon page names); an engine whose first
    # vertical slice implements only personal data (no message-archive
    # decoding yet) can still build its Pokémon section without one. Gated
    # declaratively on the profile's "messages" layout entry, matching
    # GameBuildContext's optional-input accessors, rather than probing with a
    # try/except around the build.
    abilities_dataset = None
    if (
        args.command == "build-pokemon"
        and "messages" in workflow.current.profile.layout
    ):
        abilities_dataset = workflow.build("abilities")
    relationship_index = None
    type_dataset = None
    relationship_datasets: dict[str, dict] = {}
    if args.command == "build-pokemon":
        relationship_datasets = _current_relationship_datasets(workflow.current)
        relationship_index = build_relationship_index(relationship_datasets)
        type_dataset = build_type_dataset(workflow.current.profile)
        _write_type_build(type_dataset, data_root, wiki_root)
    elif args.command == "build-moves":
        relationship_datasets = {"pokemon": workflow.current.pokemon()}
        relationship_index = build_relationship_index(relationship_datasets)
    reference_datasets = {}
    if args.command == "build-locations":
        relationship_datasets = {
            "locations": workflow.current.locations(),
            "encounters": workflow.current.encounters(),
        }
        relationship_index = build_relationship_index(relationship_datasets)
        reference_datasets = {
            "pokemon": workflow.current.pokemon(),
            "items": workflow.current.items(),
        }
    elif args.command == "build-pokemon":
        reference_datasets = dict(relationship_datasets)
        if abilities_dataset is not None:
            reference_datasets["abilities"] = abilities_dataset.current
        if move_dataset is not None:
            reference_datasets["moves"] = move_dataset
    elif args.command == "build-moves":
        reference_datasets = dict(relationship_datasets)
    reference_index = (
        ReferenceIndex.from_datasets(reference_datasets) if reference_datasets else None
    )
    kinds = tuple(
        kind for kind in kinds if kind != "abilities" or abilities_dataset is not None
    )
    for index, kind in enumerate(kinds):
        build = abilities_dataset if kind == "abilities" else workflow.build(kind)
        data_output = (
            args.data_output
            if index == 0 and args.data_output is not None
            else _dataset_output(data_root, kind)
        )
        wiki_output = (
            args.wiki_output
            if index == 0 and args.wiki_output is not None
            else wiki_root / kind
        )
        _write_dataset_build(
            kind,
            build.current,
            build.comparison,
            data_output,
            wiki_output,
            move_dataset=move_dataset,
            reference_index=reference_index,
            relationship_index=relationship_index,
            type_dataset=type_dataset,
            only_pages=dev_pages.pages_for(kind) if dev_pages else None,
        )
        if build.comparison is not None:
            comparisons[kind] = build.comparison
        else:
            comparisons.pop(kind, None)
            comparison_path = data_root / "comparisons" / f"{kind}.json"
            if comparison_path.is_file():
                comparison_path.unlink()
    render_changes_pages(comparisons, wiki_root)


def _run_full_game_build(
    args: argparse.Namespace,
    result: InspectionResult,
    *,
    workflow: GameBuildWorkflow | None = None,
) -> None:
    workflow = workflow or _create_build_workflow(args, result)
    game = workflow.current.profile.id
    data_root = args.data_root / game
    wiki_root = args.wiki_root or _profile_wiki_root(game)
    dev_pages = DevPages.load(wiki_root.parent / "dev-pages.toml") if args.dev else None
    builds = workflow.build_all()
    current_datasets = {kind: build.current for kind, build in builds.items()}
    trades = workflow.current.trades()
    if trades is not None:
        current_datasets["trades"] = trades
    reference_index = ReferenceIndex.from_datasets(current_datasets)
    relationship_index = build_relationship_index(current_datasets)
    type_dataset = build_type_dataset(workflow.current.profile)
    _write_type_build(type_dataset, data_root, wiki_root)
    comparisons = {}
    for kind, build in builds.items():
        _write_dataset_build(
            kind,
            build.current,
            build.comparison,
            _dataset_output(data_root, kind),
            wiki_root / kind,
            move_dataset=builds["moves"].current,
            reference_index=reference_index,
            relationship_index=relationship_index,
            type_dataset=type_dataset,
            only_pages=dev_pages.pages_for(kind) if dev_pages else None,
        )
        if build.comparison is not None:
            comparisons[kind] = build.comparison
    if not comparisons:
        comparison_root = data_root / "comparisons"
        if comparison_root.is_dir():
            for path in comparison_root.glob("*.json"):
                path.unlink()
    page_count = render_changes_pages(comparisons, wiki_root)
    _LOG.info(
        "Rendered %s change overview pages: %s",
        page_count,
        wiki_root / "changes",
    )


# Sections a version-family site can build, keyed to the profile layout entry
# that gates them (an empty key set means always attempted, like
# GameBuildContext.pokemon() and .items()). A section is only built when all
# sibling profiles configure
# every required layout entry, matching the declarative-gate convention
# GameBuildContext's optional-input accessors already use.
# Each kind maps to one or more alternative required-key sets (a kind
# qualifies if any one set's keys are all present) -- Locations' two very
# different implementations (Gen IV's full map-matrix-based one vs. Gen V's
# bare-minimum map-header one) both use this same gating dict.
_VERSION_FAMILY_SECTION_LAYOUT_KEYS: dict[str, tuple[tuple[str, ...], ...]] = {
    "pokemon": ((),),
    "abilities": (("messages",),),
    "items": (("item_data", "messages"),),
    "moves": (("moves",),),
    "encounters": (("encounters",),),
    "trainers": (("trainer_data", "trainer_parties"),),
    "locations": (("map_matrices",), ("map_headers",)),
}


def _run_version_family_build(
    args: argparse.Namespace,
    *,
    workflows: Mapping[str, GameBuildWorkflow] | None = None,
) -> None:
    if args.site_id is None:
        raise LocalConfigError("build family requires --site-id")
    games, versions = _version_family_inputs(args.games, args.versions)
    if workflows is None:
        registry = LocalGameRegistry.load(args.games_config)
        game_paths = {
            version: registry.get(game_id)
            for version, game_id in zip(versions, games, strict=True)
        }
        compare_to_bases = _version_family_uses_baselines(game_paths)

        current_results = {
            version: inspect_rom(game_paths[version].rom(), args.profiles_dir)
            for version in versions
        }
        unmatched = [
            version
            for version, result in current_results.items()
            if result.match is None
        ]
        if unmatched:
            raise LocalConfigError(
                "Version-family ROMs did not match game profiles: "
                f"{', '.join(unmatched)}"
            )
        profiles = tuple(
            result.match.profile
            for result in current_results.values()
            if result.match is not None
        )
        pokedb = PokeDBGeneration.load(_resolve_pokedb_path(args.pokedb, profiles))
        workflows = {}
        for version in versions:
            paths = game_paths[version]
            result = current_results[version]
            baseline = (
                inspect_rom(paths.rom(base=True), args.profiles_dir)
                if compare_to_bases
                else None
            )
            workflows[version] = GameBuildWorkflow(
                result,
                pokedb,
                baseline=baseline,
                baseline_cache_root=args.data_root / "baselines",
                refresh_baseline=args.refresh_baseline,
                current_cache_root=args.data_root / "cache",
                refresh_current=args.refresh_cache,
            )
    elif set(workflows) != set(versions):
        raise LocalConfigError(
            "Prepared version-family workflows do not match configured versions"
        )

    layouts = [workflows[version].current.profile.layout for version in versions]
    kinds = [
        kind
        for kind, alternatives in _VERSION_FAMILY_SECTION_LAYOUT_KEYS.items()
        if any(
            all(all(key in layout for key in required_keys) for layout in layouts)
            for required_keys in alternatives
        )
    ]

    merged_datasets: dict[str, dict] = {}
    merged_comparisons: dict[str, dict] = {}
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
    relationship_datasets = dict(merged_datasets)
    if trade_datasets:
        if len(trade_datasets) != len(workflows):
            raise LocalConfigError(
                "Version-family games must have matching trade capabilities"
            )
        relationship_datasets["trades"] = merge_version_family_datasets(trade_datasets)

    site_id = args.site_id
    wiki_root = args.wiki_root or _site_wiki_root(site_id)
    data_root = args.data_root / site_id
    dev_pages = DevPages.load(wiki_root.parent / "dev-pages.toml") if args.dev else None
    reference_index = ReferenceIndex.from_datasets(merged_datasets)
    relationship_index = build_relationship_index(relationship_datasets)
    move_dataset = merged_datasets.get("moves")
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
    type_dataset = type_datasets[0]
    _write_type_build(type_dataset, data_root, wiki_root)
    for kind, dataset in merged_datasets.items():
        comparison = merged_comparisons.get(kind)
        _write_dataset_build(
            kind,
            dataset,
            comparison,
            _dataset_output(data_root, kind),
            wiki_root / kind,
            move_dataset=move_dataset,
            reference_index=reference_index,
            relationship_index=relationship_index,
            type_dataset=type_dataset,
            only_pages=dev_pages.pages_for(kind) if dev_pages else None,
        )
    if merged_comparisons:
        page_count = render_changes_pages(merged_comparisons, wiki_root)
        _LOG.info(
            "Rendered %s change overview pages: %s",
            page_count,
            wiki_root / "changes",
        )


def _run_regeneration(args: argparse.Namespace) -> None:
    regeneration_started = perf_counter()
    _LOG.info("Complete regeneration started")
    if args.snapshot and not args.regenerate_all:
        raise SiteError("--snapshot requires --all")

    catalog = SiteCatalog.load(args.root)
    selected = catalog.select(
        args.site_ids,
        all_published=args.regenerate_all,
    )
    data_sites = tuple(
        site
        for site in selected
        if site.kind == "game" and site.game is not None and site.game.data_driven
    )
    registry = LocalGameRegistry.load(args.games_config) if data_sites else None
    profiles = (
        _regeneration_profiles(catalog, args.profiles_dir) if data_sites else None
    )
    pokedb_generations: dict[Path, PokeDBGeneration] = {}
    inspections: dict[Path, InspectionResult] = {}

    prepared: list[
        tuple[
            SiteDefinition,
            tuple[LocalGamePaths, ...],
            tuple[InspectionResult, ...],
            tuple[InspectionResult | None, ...],
            PokeDBGeneration,
        ]
    ] = []
    preflight_started = perf_counter()
    _LOG.info("Regeneration preflight started")
    for site in data_sites:
        assert site.game is not None
        assert profiles is not None
        pokedb_path = args.pokedb_root / f"gen{site.game.generation}"
        if not pokedb_path.is_dir():
            raise LocalConfigError(
                f"PokéDB generation output does not exist for {site.id}: "
                f"{pokedb_path.resolve()}"
            )
        resolved_pokedb = pokedb_path.resolve()
        if resolved_pokedb not in pokedb_generations:
            pokedb_generations[resolved_pokedb] = PokeDBGeneration.load(resolved_pokedb)
        pokedb = pokedb_generations[resolved_pokedb]
        assert registry is not None
        paths = tuple(registry.get(profile) for profile in site.game.profiles)
        current = []
        for profile, game_paths in zip(site.game.profiles, paths, strict=True):
            current.append(
                _validate_regeneration_rom(
                    game_paths.rom(),
                    profile,
                    args.profiles_dir,
                    profiles,
                    inspections,
                )
            )
        uses_baselines = (
            paths[0].base_rom is not None
            if len(paths) == 1
            else _version_family_uses_baselines(
                dict(zip(site.game.versions, paths, strict=True))
            )
        )
        baselines: list[InspectionResult | None] = [None] * len(paths)
        if uses_baselines:
            for index, game_paths in enumerate(paths):
                baseline = _inspect_regeneration_rom(
                    game_paths.rom(base=True),
                    args.profiles_dir,
                    profiles,
                    inspections,
                )
                if baseline.match is None:
                    raise LocalConfigError(
                        f"Base ROM for {game_paths.game_id} does not match a profile"
                    )
                baselines[index] = baseline
        prepared.append((site, paths, tuple(current), tuple(baselines), pokedb))

    _LOG.info(
        "Validated regeneration inputs for %s data-driven site(s) in %.1fs",
        f"{len(prepared):,}",
        perf_counter() - preflight_started,
    )
    for site, paths, current, baselines, pokedb in prepared:
        game = site.game
        assert game is not None
        site_started = perf_counter()
        _LOG.info("Regenerating %s", site.id)
        if len(game.profiles) == 1:
            build_args = argparse.Namespace(
                input_rom=None,
                rom_override=None,
                game=game.profiles[0],
                base=False,
                games_config=args.games_config,
                profiles_dir=args.profiles_dir,
                base_rom=None,
                hack_only=paths[0].base_rom is None,
                refresh_baseline=args.refresh,
                refresh_cache=args.refresh,
                dev=False,
                pokedb=args.pokedb_root / f"gen{game.generation}",
                data_root=args.data_root,
                wiki_root=site.config_path.parent / "wiki",
            )
            workflow = GameBuildWorkflow(
                current[0],
                pokedb,
                baseline=baselines[0],
                baseline_cache_root=args.data_root / "baselines",
                refresh_baseline=args.refresh,
                current_cache_root=args.data_root / "cache",
                refresh_current=args.refresh,
            )
            _run_full_game_build(build_args, current[0], workflow=workflow)
        else:
            build_args = argparse.Namespace(
                games=list(game.profiles),
                versions=list(game.versions),
                site_id=site.id,
                games_config=args.games_config,
                profiles_dir=args.profiles_dir,
                pokedb=args.pokedb_root / f"gen{game.generation}",
                data_root=args.data_root,
                wiki_root=site.config_path.parent / "wiki",
                refresh_baseline=args.refresh,
                refresh_cache=args.refresh,
                dev=False,
            )
            workflows = {
                version: GameBuildWorkflow(
                    result,
                    pokedb,
                    baseline=baseline,
                    baseline_cache_root=args.data_root / "baselines",
                    refresh_baseline=args.refresh,
                    current_cache_root=args.data_root / "cache",
                    refresh_current=args.refresh,
                )
                for version, result, baseline in zip(
                    game.versions, current, baselines, strict=True
                )
            }
            _run_version_family_build(build_args, workflows=workflows)
        _LOG.info(
            "Regenerated %s in %.1fs",
            site.id,
            perf_counter() - site_started,
        )

    with timed_operation(_LOG, "Site builds"):
        built = build_sites(
            catalog,
            args.output,
            site_ids=args.site_ids,
            build_all=args.regenerate_all,
        )
    for site in built:
        _LOG.info("Built %s: %s", site.id, site.output_path(args.output.resolve()))

    with timed_operation(_LOG, "Site audit"):
        report = audit_site(
            args.output,
            max_html_bytes=args.max_page_kb * 1024,
            max_images_per_page=args.max_images,
            base_url=args.base_url,
        )
    _report_site_audit(report)

    if args.snapshot:
        with timed_operation(_LOG, "Generated wiki snapshot"):
            count = create_generated_wiki_snapshot(
                args.root,
                args.snapshot_output,
                catalog=catalog,
            )
        _LOG.info(
            "Archived %s generated wiki files: %s",
            f"{count:,}",
            args.snapshot_output,
        )
    _LOG.info(
        "Complete regeneration finished in %.1fs",
        perf_counter() - regeneration_started,
    )


def _validate_regeneration_rom(
    path: Path,
    expected_profile: str,
    profiles_dir: Path,
    profiles: ProfileRepository,
    inspections: dict[Path, InspectionResult],
) -> InspectionResult:
    result = _inspect_regeneration_rom(
        path,
        profiles_dir,
        profiles,
        inspections,
    )
    actual_profile = result.match.profile.id if result.match is not None else None
    if actual_profile != expected_profile:
        actual = actual_profile or "no profile"
        raise LocalConfigError(
            f"ROM for {expected_profile} matched {actual}, not {expected_profile}"
        )
    return result


def _inspect_regeneration_rom(
    path: Path,
    profiles_dir: Path,
    profiles: ProfileRepository,
    inspections: dict[Path, InspectionResult],
) -> InspectionResult:
    resolved = path.resolve()
    if resolved not in inspections:
        inspections[resolved] = inspect_rom(
            resolved,
            profiles_dir,
            profiles=profiles,
        )
    return inspections[resolved]


def _regeneration_profiles(
    catalog: SiteCatalog,
    profiles_dir: Path,
) -> ProfileRepository:
    if (
        catalog.profile_repository is not None
        and profiles_dir.resolve() == (catalog.root / "profiles").resolve()
    ):
        return catalog.profile_repository
    return ProfileRepository.load(profiles_dir)


def _report_site_audit(report: SiteAuditReport) -> None:
    warning_counts = Counter(issue.code for issue in report.warnings)
    if _LOG.isEnabledFor(logging.DEBUG):
        for issue in report.warnings:
            _LOG.warning("%s", issue.format())
    elif warning_counts:
        summary = ", ".join(
            f"{code}={count:,}" for code, count in sorted(warning_counts.items())
        )
        _LOG.warning(
            "Site audit found %s warning(s): %s; rerun with --verbose for details",
            f"{len(report.warnings):,}",
            summary,
        )
    displayed_errors = report.errors[:100]
    for issue in displayed_errors:
        _LOG.error("%s", issue.format())
    if len(report.errors) > len(displayed_errors):
        _LOG.error(
            "... %s additional error(s) omitted",
            f"{len(report.errors) - len(displayed_errors):,}",
        )
    largest = report.largest_page
    largest_text = (
        f"; largest: {largest[0]} ({largest[1] / 1024:.1f} KiB)" if largest else ""
    )
    _LOG.info(
        "Audited %s pages and %s links%s",
        f"{report.page_count:,}",
        f"{report.link_count:,}",
        largest_text,
    )
    if not report.ok:
        raise SiteError(f"site audit found {len(report.errors):,} error(s)")


def _version_family_inputs(
    raw_games: Sequence[str], raw_versions: Sequence[str] | None
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    games = tuple(raw_games)
    versions = tuple(raw_versions or games)
    if len(games) < 2:
        raise LocalConfigError("Version-family builds require at least two games")
    if len(versions) != len(games):
        raise LocalConfigError(
            "--versions must contain one label for every --games entry"
        )
    if len(set(versions)) != len(versions):
        raise LocalConfigError("Version labels must be unique")
    return games, versions


def _version_family_uses_baselines(
    game_paths: Mapping[str, LocalGamePaths],
) -> bool:
    configured_baselines = {
        version: paths.base_rom is not None for version, paths in game_paths.items()
    }
    if len(set(configured_baselines.values())) != 1:
        raise LocalConfigError(
            "Version-family builds require every game to define base_rom or none"
        )
    return all(configured_baselines.values())


def _run_baseline_build(args: argparse.Namespace) -> None:
    paths = LocalGameRegistry.load(args.games_config).get(args.game)
    result = inspect_rom(paths.rom(base=True), args.profiles_dir)
    if result.match is None:
        raise LocalConfigError("The configured base ROM did not match a game profile")
    pokedb = PokeDBGeneration.load(
        _resolve_pokedb_path(args.pokedb, (result.match.profile,))
    )
    cache_root = args.data_root / "baselines" / result.match.profile.id
    context = GameBuildContext(
        result, pokedb, cache_root=cache_root, refresh=args.refresh
    )
    for kind in args.scope:
        getattr(context, kind)()
    print(
        f"Cached {len(args.scope)} baseline dataset groups for "
        f"{result.match.profile.id}: {cache_root}"
    )


def _resolve_pokedb_path(
    configured: Path | None,
    profiles: Sequence[GameProfile],
) -> Path:
    if configured is not None:
        return configured
    generations = {get_engine(profile.engine).generation for profile in profiles}
    if None in generations:
        engines = ", ".join(sorted({profile.engine for profile in profiles}))
        raise LocalConfigError(
            f"Engine generation metadata is missing for: {engines}; specify --pokedb"
        )
    if len(generations) != 1:
        raise LocalConfigError(
            "Selected profiles use different generations; specify compatible profiles"
        )
    generation = generations.pop()
    return Path("../pokedb/.output") / f"gen{generation}"


def _profile_wiki_root(profile_id: str, *, root: Path = Path(".")) -> Path:
    resolved_root = root.resolve()
    if not (resolved_root / "sites").is_dir():
        return Path("sites/games") / profile_id / "wiki"
    catalog = SiteCatalog.load(resolved_root)
    matches = [
        site
        for site in catalog.sites
        if site.game is not None
        and site.game.data_driven
        and profile_id in site.game.profiles
    ]
    if len(matches) > 1:
        site_ids = ", ".join(site.id for site in matches)
        raise SiteError(
            f"Profile {profile_id} belongs to multiple game sites: {site_ids}"
        )
    if matches:
        return matches[0].config_path.parent / "wiki"
    return Path("sites/games") / profile_id / "wiki"


def _site_wiki_root(site_id: str, *, root: Path = Path(".")) -> Path:
    resolved_root = root.resolve()
    if (resolved_root / "sites").is_dir():
        catalog = SiteCatalog.load(resolved_root)
        matches = [site for site in catalog.sites if site.id == site_id]
        if matches:
            return matches[0].config_path.parent / "wiki"
    return Path("sites/games") / site_id / "wiki"


def _write_dataset_build(
    kind: str,
    dataset: dict,
    comparison: dict | None,
    data_output: Path,
    wiki_output: Path,
    *,
    move_dataset: dict | None = None,
    reference_index: ReferenceIndex | None = None,
    relationship_index: RelationshipIndex | None = None,
    type_dataset: dict | None = None,
    only_pages: frozenset[str] | None = None,
) -> None:
    write_enriched_dataset(dataset, data_output)
    if comparison is not None:
        comparison_output = data_output.parent.parent / "comparisons" / f"{kind}.json"
        write_comparison_dataset(comparison, comparison_output)
    write_public_dataset(wiki_output.parent, kind, dataset, comparison)
    renderer = {
        "pokemon": render_pokemon_pages,
        "abilities": render_ability_pages,
        "moves": render_move_pages,
        "items": render_item_pages,
        "encounters": render_encounter_pages,
        "trainers": render_trainer_pages,
        "locations": render_location_pages,
    }[kind]
    if kind == "pokemon":
        page_count = renderer(
            dataset,
            wiki_output,
            comparison,
            move_dataset,
            reference_index,
            relationship_index,
            type_dataset,
            only_pages=only_pages,
        )
    elif kind in {"moves", "locations"}:
        page_count = renderer(
            dataset,
            wiki_output,
            comparison,
            reference_index,
            relationship_index,
            only_pages=only_pages,
        )
    else:
        page_count = renderer(
            dataset,
            wiki_output,
            comparison,
            reference_index,
            only_pages=only_pages,
        )
    _LOG.info(
        "Wrote %s %s records: %s",
        len(dataset["records"]),
        kind,
        data_output,
    )
    _LOG.info("Rendered %s %s pages: %s", page_count, kind, wiki_output)


def _write_type_build(
    dataset: dict,
    data_root: Path,
    wiki_root: Path,
) -> None:
    data_output = _dataset_output(data_root, "types")
    write_enriched_dataset(dataset, data_output)
    write_public_dataset(wiki_root, "types", dataset, None)
    page_count = render_type_chart(dataset, wiki_root / "types")
    _LOG.info("Wrote %s types: %s", len(dataset["records"]), data_output)
    _LOG.info(
        "Rendered %s type chart page: %s",
        page_count,
        wiki_root / "types",
    )


def _current_relationship_datasets(
    context: GameBuildContext,
) -> dict[str, dict]:
    datasets = {
        "pokemon": context.pokemon(),
        "encounters": context.encounters(),
        "trainers": context.trainers(),
        "locations": context.locations(),
        "items": context.items(),
        "trades": context.trades(),
    }
    return {kind: dataset for kind, dataset in datasets.items() if dataset is not None}


def _dataset_output(data_root: Path, kind: str) -> Path:
    filename = "raw.json" if kind == "locations" else "enriched.json"
    return data_root / kind / filename


def _load_comparisons(root: Path) -> dict[str, dict]:
    comparisons = {}
    if not root.is_dir():
        return comparisons
    for path in root.glob("*.json"):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(value, dict) and isinstance(value.get("kind"), str):
            comparisons[_comparison_workflow_kind(value["kind"])] = value
    return comparisons


def _comparison_workflow_kind(kind: str) -> str:
    return "encounters" if kind == "wild_encounters" else kind


def _resolve_input_rom(args: argparse.Namespace) -> Path:
    if args.input_rom is not None and args.rom_override is not None:
        raise LocalConfigError("Specify a positional ROM path or --rom, not both")
    explicit = args.rom_override or args.input_rom
    if explicit is not None:
        resolved = explicit.resolve()
        if not resolved.is_file():
            raise LocalConfigError(f"ROM image does not exist: {resolved}")
        return resolved
    if not args.game:
        raise LocalConfigError(
            "Specify a ROM path or select a configured game with --game"
        )
    game = LocalGameRegistry.load(args.games_config).get(args.game)
    return game.rom(base=args.base)


def _add_site_root_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="repository root containing portal and games",
    )


def _print_sites(
    catalog: SiteCatalog,
    *,
    as_json: bool = False,
    published_only: bool = False,
) -> None:
    sites = catalog.published() if published_only else catalog.sites
    if as_json:
        print(
            json.dumps(
                [
                    {
                        "id": site.id,
                        "data_driven": bool(site.game and site.game.data_driven),
                    }
                    for site in sites
                ],
                separators=(",", ":"),
            )
        )
        return
    for site in sites:
        state = "published" if site.published else "draft"
        location = "/" if not site.slug else f"/{site.slug}/"
        print(f"{site.id:<24} {state:<9} {location}  {site.name}")


def _print_inspection(result: InspectionResult, *, as_json: bool) -> None:
    data = result.to_dict()
    if as_json:
        print(json.dumps(data, indent=2, sort_keys=True))
        return

    profile = data["profile"]
    print(f"Title: {data['header']['title']}")
    print(f"Game code: {data['header']['game_code']}")
    print(f"ROM version: {data['header']['rom_version']}")
    print(f"Size: {data['size']} bytes")
    print(f"Files: {data['header']['filesystem_file_count']}")
    print(f"SHA-256: {data['hashes']['sha256']}")
    if profile:
        print(f"Profile: {profile['name']} ({profile['variant']})")
        print(f"Engine: {profile['engine']}")
    else:
        print("Profile: unknown")

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

from romwiki.errors import RomWikiError
from romwiki.pipeline.abilities import build_ability_dataset, write_ability_dataset
from romwiki.pipeline.encounters import (
    extract_encounter_dataset,
    write_encounter_dataset,
)
from romwiki.pipeline.evolutions import (
    extract_evolution_dataset,
    write_evolution_dataset,
)
from romwiki.pipeline.egg_moves import (
    extract_egg_move_dataset,
    write_egg_move_dataset,
)
from romwiki.pipeline.identify import InspectionResult, inspect_rom
from romwiki.pipeline.enrich import (
    enrich_encounter_dataset,
    enrich_move_dataset,
    enrich_personal_dataset,
    enrich_trainer_dataset,
    write_enriched_dataset,
)
from romwiki.pipeline.locations import extract_location_dataset, write_location_dataset
from romwiki.pipeline.learnsets import extract_learnset_dataset, write_learnset_dataset
from romwiki.pipeline.moves import extract_move_dataset, write_move_dataset
from romwiki.pipeline.manifest import create_manifest, write_manifest
from romwiki.pipeline.machines import extract_machine_dataset, write_machine_dataset
from romwiki.pipeline.personal import extract_personal_dataset, write_personal_dataset
from romwiki.pipeline.trainers import extract_trainer_dataset, write_trainer_dataset
from romwiki.pipeline.tutors import extract_tutor_dataset, write_tutor_dataset
from romwiki.renderers.mkdocs import (
    render_ability_pages,
    render_encounter_pages,
    render_location_pages,
    render_move_pages,
    render_pokemon_pages,
    render_trainer_pages,
)
from romwiki.sites import SiteCatalog, build_sites
from romwiki.sources import PokeDBGeneration


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="romwiki",
        description="Extract structured Pokémon ROM data for static wikis.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="identify a ROM image")
    _add_input_arguments(inspect_parser)
    inspect_parser.add_argument("--json", action="store_true", help="emit JSON")

    manifest_parser = subparsers.add_parser(
        "manifest", help="write a machine-readable input manifest"
    )
    _add_input_arguments(manifest_parser)
    manifest_parser.add_argument(
        "--output",
        type=Path,
        default=Path("build/data/manifest.json"),
        help="manifest output path",
    )

    personal_parser = subparsers.add_parser(
        "extract-personal", help="extract normalized Pokémon personal data"
    )
    _add_input_arguments(personal_parser)
    personal_parser.add_argument(
        "--output",
        type=Path,
        help="dataset output path (defaults below build/data/<profile>/pokemon)",
    )

    encounter_parser = subparsers.add_parser(
        "extract-encounters", help="extract normalized wild encounter data"
    )
    _add_input_arguments(encounter_parser)
    encounter_parser.add_argument(
        "--output",
        type=Path,
        help="dataset output path (defaults below build/data/<profile>/encounters)",
    )

    trainer_parser = subparsers.add_parser(
        "extract-trainers", help="extract normalized trainer and party data"
    )
    _add_input_arguments(trainer_parser)
    trainer_parser.add_argument(
        "--output",
        type=Path,
        help="dataset output path (defaults below build/data/<profile>/trainers)",
    )

    location_parser = subparsers.add_parser(
        "extract-locations", help="extract normalized map locations and navigation"
    )
    _add_input_arguments(location_parser)
    location_parser.add_argument(
        "--output",
        type=Path,
        help="dataset output path (defaults below build/data/<profile>/locations)",
    )

    move_parser = subparsers.add_parser(
        "extract-moves", help="extract normalized move mechanics"
    )
    _add_input_arguments(move_parser)
    move_parser.add_argument(
        "--output",
        type=Path,
        help="dataset output path (defaults below build/data/<profile>/moves)",
    )

    learnset_parser = subparsers.add_parser(
        "extract-learnsets", help="extract normalized level-up learnsets"
    )
    _add_input_arguments(learnset_parser)
    learnset_parser.add_argument(
        "--output",
        type=Path,
        help="dataset output path (defaults below build/data/<profile>/pokemon)",
    )

    egg_move_parser = subparsers.add_parser(
        "extract-egg-moves", help="extract normalized Pokémon egg moves"
    )
    _add_input_arguments(egg_move_parser)
    egg_move_parser.add_argument(
        "--output",
        type=Path,
        help="dataset output path (defaults below build/data/<profile>/pokemon)",
    )

    evolution_parser = subparsers.add_parser(
        "extract-evolutions", help="extract normalized Pokémon evolutions"
    )
    _add_input_arguments(evolution_parser)
    evolution_parser.add_argument(
        "--output",
        type=Path,
        help="dataset output path (defaults below build/data/<profile>/pokemon)",
    )

    machine_parser = subparsers.add_parser(
        "extract-machines", help="extract TM/HM move assignments"
    )
    _add_input_arguments(machine_parser)
    machine_parser.add_argument(
        "--output",
        type=Path,
        help="dataset output path (defaults below build/data/<profile>/machines)",
    )

    tutor_parser = subparsers.add_parser(
        "extract-tutors", help="extract move tutor assignments and compatibility"
    )
    _add_input_arguments(tutor_parser)
    tutor_parser.add_argument(
        "--output",
        type=Path,
        help="dataset output path (defaults below build/data/<profile>/tutors)",
    )

    pokemon_parser = subparsers.add_parser(
        "build-pokemon", help="extract, enrich, and render Pokémon pages"
    )
    _add_input_arguments(pokemon_parser)
    pokemon_parser.add_argument(
        "--pokedb",
        type=Path,
        default=Path("../pokedb/.output/gen4"),
        help="PokéDB generation output directory",
    )
    pokemon_parser.add_argument("--data-output", type=Path)
    pokemon_parser.add_argument("--wiki-output", type=Path)

    build_encounters_parser = subparsers.add_parser(
        "build-encounters", help="extract, enrich, and render wild encounter pages"
    )
    _add_input_arguments(build_encounters_parser)
    build_encounters_parser.add_argument(
        "--pokedb",
        type=Path,
        default=Path("../pokedb/.output/gen4"),
        help="PokéDB generation output directory",
    )
    build_encounters_parser.add_argument("--data-output", type=Path)
    build_encounters_parser.add_argument("--wiki-output", type=Path)

    build_trainers_parser = subparsers.add_parser(
        "build-trainers", help="extract, enrich, and render trainer pages"
    )
    _add_input_arguments(build_trainers_parser)
    build_trainers_parser.add_argument(
        "--pokedb",
        type=Path,
        default=Path("../pokedb/.output/gen4"),
        help="PokéDB generation output directory",
    )
    build_trainers_parser.add_argument("--data-output", type=Path)
    build_trainers_parser.add_argument("--wiki-output", type=Path)

    build_locations_parser = subparsers.add_parser(
        "build-locations", help="extract and render location navigation pages"
    )
    _add_input_arguments(build_locations_parser)
    build_locations_parser.add_argument("--data-output", type=Path)
    build_locations_parser.add_argument("--wiki-output", type=Path)

    build_moves_parser = subparsers.add_parser(
        "build-moves", help="extract, enrich, and render move pages"
    )
    _add_input_arguments(build_moves_parser)
    build_moves_parser.add_argument(
        "--pokedb",
        type=Path,
        default=Path("../pokedb/.output/gen4"),
        help="PokéDB generation output directory",
    )
    build_moves_parser.add_argument("--data-output", type=Path)
    build_moves_parser.add_argument("--wiki-output", type=Path)

    site_parser = subparsers.add_parser(
        "site", help="list or build independently configured wiki sites"
    )
    site_subparsers = site_parser.add_subparsers(dest="site_command", required=True)
    list_parser = site_subparsers.add_parser("list", help="list configured sites")
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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command in {
            "inspect",
            "manifest",
            "extract-personal",
            "extract-encounters",
            "extract-trainers",
            "extract-locations",
            "extract-moves",
            "extract-learnsets",
            "extract-egg-moves",
            "extract-evolutions",
            "extract-machines",
            "extract-tutors",
            "build-pokemon",
            "build-encounters",
            "build-trainers",
            "build-locations",
            "build-moves",
        }:
            result = inspect_rom(args.rom, args.profiles_dir)
        if args.command == "inspect":
            _print_inspection(result, as_json=args.json)
        elif args.command == "manifest":
            write_manifest(create_manifest(result), args.output)
            print(f"Wrote manifest: {args.output}")
        elif args.command == "extract-personal":
            dataset = extract_personal_dataset(result)
            output = args.output or (
                Path("build/data")
                / dataset["game"]
                / "pokemon"
                / "personal.json"
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
            dataset = extract_location_dataset(result)
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
        elif args.command == "extract-learnsets":
            dataset = extract_learnset_dataset(result)
            output = args.output or (
                Path("build/data")
                / dataset["game"]
                / "pokemon"
                / "learnsets.json"
            )
            write_learnset_dataset(dataset, output)
            print(f"Wrote {dataset['record_count']} learnsets: {output}")
        elif args.command == "extract-egg-moves":
            dataset = extract_egg_move_dataset(result)
            output = args.output or (
                Path("build/data")
                / dataset["game"]
                / "pokemon"
                / "egg-moves.json"
            )
            write_egg_move_dataset(dataset, output)
            print(
                f"Wrote {dataset['record_count']} egg move sets with "
                f"{dataset['move_reference_count']} move references: {output}"
            )
        elif args.command == "extract-evolutions":
            dataset = extract_evolution_dataset(result)
            output = args.output or (
                Path("build/data")
                / dataset["game"]
                / "pokemon"
                / "evolutions.json"
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
        elif args.command == "build-pokemon":
            personal = extract_personal_dataset(result)
            learnsets = extract_learnset_dataset(result)
            egg_moves = extract_egg_move_dataset(result)
            evolutions = extract_evolution_dataset(result)
            machines = extract_machine_dataset(result)
            tutors = extract_tutor_dataset(result)
            pokedb = PokeDBGeneration.load(args.pokedb)
            enriched = enrich_personal_dataset(
                personal,
                pokedb,
                learnsets,
                evolutions,
                machines,
                tutors,
                egg_moves,
                type_names=(
                    result.match.profile.type_names if result.match else None
                ),
                move_names=(
                    result.match.profile.move_names if result.match else None
                ),
                sprite_version=(
                    result.match.profile.sprite_version if result.match else None
                ),
            )
            data_output = args.data_output or (
                Path("build/data")
                / enriched["game"]
                / "pokemon"
                / "enriched.json"
            )
            wiki_output = args.wiki_output or (
                Path("sites/games") / enriched["game"] / "wiki" / "pokemon"
            )
            write_enriched_dataset(enriched, data_output)
            page_count = render_pokemon_pages(enriched, wiki_output)
            abilities = build_ability_dataset(enriched, pokedb)
            ability_data_output = (
                data_output.parent.parent / "abilities" / "enriched.json"
            )
            ability_wiki_output = wiki_output.parent / "abilities"
            write_ability_dataset(abilities, ability_data_output)
            ability_page_count = render_ability_pages(abilities, ability_wiki_output)
            print(f"Wrote {enriched['record_count']} enriched records: {data_output}")
            print(f"Rendered {page_count} Pokémon pages: {wiki_output}")
            print(
                f"Wrote {abilities['record_count']} ability records: "
                f"{ability_data_output}"
            )
            print(
                f"Rendered {ability_page_count} ability pages: {ability_wiki_output}"
            )
        elif args.command == "build-encounters":
            extracted = extract_encounter_dataset(result)
            enriched = enrich_encounter_dataset(
                extracted, PokeDBGeneration.load(args.pokedb)
            )
            data_output = args.data_output or (
                Path("build/data")
                / enriched["game"]
                / "encounters"
                / "enriched.json"
            )
            wiki_output = args.wiki_output or (
                Path("sites/games") / enriched["game"] / "wiki" / "encounters"
            )
            write_enriched_dataset(enriched, data_output)
            page_count = render_encounter_pages(enriched, wiki_output)
            print(f"Wrote {enriched['record_count']} enriched records: {data_output}")
            print(f"Rendered {page_count} encounter pages: {wiki_output}")
        elif args.command == "build-trainers":
            extracted = extract_trainer_dataset(result)
            enriched = enrich_trainer_dataset(
                extracted,
                PokeDBGeneration.load(args.pokedb),
                move_names=(
                    result.match.profile.move_names if result.match else None
                ),
            )
            data_output = args.data_output or (
                Path("build/data") / enriched["game"] / "trainers" / "enriched.json"
            )
            wiki_output = args.wiki_output or (
                Path("sites/games") / enriched["game"] / "wiki" / "trainers"
            )
            write_enriched_dataset(enriched, data_output)
            page_count = render_trainer_pages(enriched, wiki_output)
            print(f"Wrote {enriched['record_count']} enriched records: {data_output}")
            print(f"Rendered {page_count} trainer pages: {wiki_output}")
        elif args.command == "build-locations":
            dataset = extract_location_dataset(result)
            data_output = args.data_output or (
                Path("build/data") / dataset["game"] / "locations" / "raw.json"
            )
            wiki_output = args.wiki_output or (
                Path("sites/games") / dataset["game"] / "wiki" / "locations"
            )
            write_location_dataset(dataset, data_output)
            page_count = render_location_pages(dataset, wiki_output)
            print(f"Wrote {dataset['record_count']} location records: {data_output}")
            print(f"Rendered {page_count} location pages: {wiki_output}")
        elif args.command == "build-moves":
            extracted = extract_move_dataset(result)
            machines = extract_machine_dataset(result)
            tutors = extract_tutor_dataset(result)
            egg_moves = extract_egg_move_dataset(result)
            enriched = enrich_move_dataset(
                extracted,
                PokeDBGeneration.load(args.pokedb),
                machines,
                tutors,
                egg_moves,
                type_names=(
                    result.match.profile.type_names if result.match else None
                ),
                move_names=(
                    result.match.profile.move_names if result.match else None
                ),
            )
            data_output = args.data_output or (
                Path("build/data") / enriched["game"] / "moves" / "enriched.json"
            )
            wiki_output = args.wiki_output or (
                Path("sites/games") / enriched["game"] / "wiki" / "moves"
            )
            write_enriched_dataset(enriched, data_output)
            page_count = render_move_pages(enriched, wiki_output)
            print(f"Wrote {enriched['record_count']} enriched records: {data_output}")
            print(f"Rendered {page_count} move pages: {wiki_output}")
        elif args.command == "site":
            catalog = SiteCatalog.load(args.root)
            if args.site_command == "list":
                _print_sites(catalog)
            elif args.site_command == "build":
                built = build_sites(
                    catalog,
                    args.output,
                    site_ids=args.site_ids,
                    build_all=args.build_all,
                )
                for site in built:
                    print(f"Built {site.id}: {site.output_path(args.output.resolve())}")
        return 0
    except RomWikiError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


def _add_input_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("rom", type=Path, help="path to a locally supplied ROM image")
    parser.add_argument(
        "--profiles-dir",
        type=Path,
        default=Path("profiles"),
        help="directory containing game and hack profiles",
    )


def _add_site_root_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="repository root containing portal and games",
    )


def _print_sites(catalog: SiteCatalog) -> None:
    for site in catalog.sites:
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

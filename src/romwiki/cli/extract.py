"""`romwiki extract`: write one normalized single-ROM audit dataset."""

from __future__ import annotations

import argparse
from pathlib import Path

from romwiki.cli.common import (
    DEFAULT_DATA_ROOT,
    SubParsers,
    add_input_arguments,
    inspect_input,
)
from romwiki.engines.registry import get_engine
from romwiki.pipeline.extraction.egg_moves import extract_egg_move_dataset
from romwiki.pipeline.extraction.encounters import extract_encounter_dataset
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
from romwiki.pipeline.io import write_dataset
from romwiki.util.errors import LocalConfigError


def add_parser(subparsers: SubParsers) -> None:
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
        add_input_arguments(extract_kind_parser)
        extract_kind_parser.add_argument(
            "--output",
            type=Path,
            help=(
                "dataset output path "
                f"(default: below build/data/<profile>/{output_group})"
            ),
        )
        extract_kind_parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> None:
    extract(args.extract_kind, inspect_input(args), args.output)


def extract(kind: str, result: InspectionResult, output: Path | None) -> None:
    if kind == "personal":
        dataset = extract_personal_dataset(result)
        output = output or (
            DEFAULT_DATA_ROOT / dataset["game"] / "pokemon" / "personal.json"
        )
        write_dataset(dataset, output)
        print(f"Wrote {dataset['record_count']} personal records: {output}")
    elif kind == "encounters":
        dataset = extract_encounter_dataset(result)
        output = output or (
            DEFAULT_DATA_ROOT / dataset["game"] / "encounters" / "raw.json"
        )
        write_dataset(dataset, output)
        print(f"Wrote {dataset['record_count']} encounter records: {output}")
    elif kind == "trainers":
        dataset = extract_trainer_dataset(result)
        output = output or (
            DEFAULT_DATA_ROOT / dataset["game"] / "trainers" / "raw.json"
        )
        write_dataset(dataset, output)
        print(f"Wrote {dataset['record_count']} trainer records: {output}")
    elif kind == "locations":
        if result.match is None:
            raise LocalConfigError("The ROM did not match a game profile")
        profile = result.match.profile
        engine = get_engine(profile.engine)
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
            trade_dataset=(
                extract_npc_trade_dataset(result)
                if "detached-npc-trades" in engine.capabilities
                and "npc_trades" in profile.layout
                else None
            ),
        )
        output = output or (
            DEFAULT_DATA_ROOT / dataset["game"] / "locations" / "raw.json"
        )
        write_dataset(dataset, output)
        print(f"Wrote {dataset['record_count']} location records: {output}")
    elif kind == "moves":
        dataset = extract_move_dataset(result)
        output = output or (DEFAULT_DATA_ROOT / dataset["game"] / "moves" / "raw.json")
        write_dataset(dataset, output)
        print(f"Wrote {dataset['record_count']} move records: {output}")
    elif kind == "items":
        dataset = extract_item_dataset(result)
        output = output or (DEFAULT_DATA_ROOT / dataset["game"] / "items" / "raw.json")
        write_dataset(dataset, output)
        print(f"Wrote {dataset['record_count']} item records: {output}")
    elif kind == "learnsets":
        dataset = extract_learnset_dataset(result)
        output = output or (
            DEFAULT_DATA_ROOT / dataset["game"] / "pokemon" / "learnsets.json"
        )
        write_dataset(dataset, output)
        print(f"Wrote {dataset['record_count']} learnsets: {output}")
    elif kind == "egg-moves":
        dataset = extract_egg_move_dataset(result)
        output = output or (
            DEFAULT_DATA_ROOT / dataset["game"] / "pokemon" / "egg-moves.json"
        )
        write_dataset(dataset, output)
        print(
            f"Wrote {dataset['record_count']} egg move sets with "
            f"{dataset['move_reference_count']} move references: {output}"
        )
    elif kind == "evolutions":
        dataset = extract_evolution_dataset(result)
        output = output or (
            DEFAULT_DATA_ROOT / dataset["game"] / "pokemon" / "evolutions.json"
        )
        write_dataset(dataset, output)
        print(f"Wrote {dataset['record_count']} evolution records: {output}")
    elif kind == "machines":
        dataset = extract_machine_dataset(result)
        output = output or (
            DEFAULT_DATA_ROOT / dataset["game"] / "machines" / "raw.json"
        )
        write_dataset(dataset, output)
        print(f"Wrote {dataset['record_count']} machine records: {output}")
    elif kind == "tutors":
        dataset = extract_tutor_dataset(result)
        output = output or (DEFAULT_DATA_ROOT / dataset["game"] / "tutors" / "raw.json")
        write_dataset(dataset, output)
        print(
            f"Wrote {dataset['record_count']} shard tutor records, "
            f"{dataset['special_record_count']} special tutor records, and "
            f"{dataset['compatibility_record_count']} shard compatibility "
            f"rows plus {dataset['special_compatibility_record_count']} "
            f"special compatibility rows: "
            f"{output}"
        )
    elif kind == "pickup":
        dataset = extract_pickup_dataset(result)
        output = output or (DEFAULT_DATA_ROOT / dataset["game"] / "pickup" / "raw.json")
        write_dataset(dataset, output)
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

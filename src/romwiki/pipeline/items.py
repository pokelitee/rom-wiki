from __future__ import annotations

from pathlib import Path
from typing import Any

from romwiki.engines.gen4_dppt import (
    GEN4_ITEM_FIELD_USE_NAMES,
    GEN4_ITEM_POCKET_NAMES,
    find_item_archive_members,
    parse_english_message_archive,
    parse_item_record,
)
from romwiki.util.errors import DataSourceError, ProfileError
from romwiki.util.json_io import write_json_atomic
from romwiki.pipeline.identify import InspectionResult
from romwiki.platforms.nds import NarcArchive, NintendoDSFileSystem
from romwiki.sources import PokeDBGeneration


def extract_item_dataset(result: InspectionResult) -> dict[str, Any]:
    if result.match is None:
        raise ProfileError("A known game profile is required for item extraction")
    profile = result.match.profile
    try:
        item_archive_path = profile.layout["item_data"]
        message_archive_path = profile.layout["messages"]
        item_names_member = profile.parameters["item_names_member"]
        type_names_member = profile.parameters["type_names_member"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} is missing item metadata: {error.args[0]}"
        ) from error

    filesystem = NintendoDSFileSystem.from_image(result.image)
    item_archive = NarcArchive.from_bytes(filesystem.read(item_archive_path))
    messages = NarcArchive.from_bytes(filesystem.read(message_archive_path))
    item_names = parse_english_message_archive(messages.read(item_names_member))
    type_names = parse_english_message_archive(messages.read(type_names_member))
    with result.image.path.open("rb") as stream:
        stream.seek(result.image.header.arm9_offset)
        arm9_data = stream.read(result.image.header.arm9_size)
    map_offset, data_members = find_item_archive_members(
        arm9_data,
        item_count=len(item_names),
        data_member_count=len(item_archive.members),
    )

    records = []
    for item_id, data_member in enumerate(data_members):
        parsed = parse_item_record(
            item_archive.read(data_member),
            item_id=item_id,
            data_archive_member=data_member,
            archive_path=item_archive_path,
        ).to_dict()
        pocket_id = parsed["field_pocket_id"]
        field_use_id = parsed["field_use_function_id"]
        natural_gift_type_id = parsed["natural_gift_type_id"]
        if pocket_id >= len(GEN4_ITEM_POCKET_NAMES):
            raise DataSourceError(f"Unknown Gen IV item pocket ID: {pocket_id}")
        if field_use_id >= len(GEN4_ITEM_FIELD_USE_NAMES):
            raise DataSourceError(
                f"Unknown Gen IV item field-use function ID: {field_use_id}"
            )
        if natural_gift_type_id != 31 and natural_gift_type_id >= len(type_names):
            raise DataSourceError(
                f"Unknown Gen IV Natural Gift type ID: {natural_gift_type_id}"
            )
        records.append(
            {
                **parsed,
                "name": item_names[item_id],
                "public": item_id > 0 and data_member > 0,
                "pocket": {
                    "id": pocket_id,
                    "name": GEN4_ITEM_POCKET_NAMES[pocket_id],
                },
                "field_use": {
                    "id": field_use_id,
                    "name": GEN4_ITEM_FIELD_USE_NAMES[field_use_id],
                },
                "natural_gift_type": (
                    None
                    if natural_gift_type_id == 31
                    else {
                        "id": natural_gift_type_id,
                        "name": type_names[natural_gift_type_id],
                    }
                ),
            }
        )

    return {
        "schema_version": 1,
        "game": profile.id,
        "dataset": "items_raw",
        "record_count": len(records),
        "public_record_count": sum(record["public"] for record in records),
        "source": {
            "rom_sha256": result.image.hashes.sha256,
            "archive": item_archive_path,
            "item_archive_map": {
                "source": "arm9",
                "offset": map_offset,
                "record_count": len(data_members),
            },
            "item_names": {
                "archive": message_archive_path,
                "member": item_names_member,
            },
            "type_names": {
                "archive": message_archive_path,
                "member": type_names_member,
            },
        },
        "records": records,
    }


def write_item_dataset(dataset: dict[str, Any], output_path: Path) -> None:
    write_json_atomic(output_path, dataset)


def build_item_dataset(
    item_dataset: dict[str, Any],
    pokedb: PokeDBGeneration,
    pokemon_dataset: dict[str, Any],
    trainer_dataset: dict[str, Any],
    location_dataset: dict[str, Any],
) -> dict[str, Any]:
    game = item_dataset.get("game")
    for label, dataset in (
        ("Pokémon", pokemon_dataset),
        ("trainer", trainer_dataset),
        ("location", location_dataset),
    ):
        if dataset.get("game") != game:
            raise DataSourceError(f"Item and {label} datasets must be for the same game")

    relationships: dict[int, dict[str, list[dict[str, Any]]]] = {}

    def add(item_id: int, kind: str, value: dict[str, Any]) -> None:
        if not item_id:
            return
        relationships.setdefault(item_id, {}).setdefault(kind, []).append(value)

    for pokemon in pokemon_dataset["records"]:
        if not pokemon["public"]:
            continue
        reference = {
            "member": pokemon["member"],
            "national_dex_id": pokemon["national_dex_id"],
            "slug": pokemon["slug"],
            "name": pokemon["name"],
        }
        for held_item in pokemon["held_items"]:
            add(
                held_item["id"],
                "wild_held_by",
                {**reference, "rarity": held_item["rarity"]},
            )
        for evolution in pokemon.get("evolutions", []):
            parameter = evolution.get("parameter_data")
            if parameter and parameter.get("kind") == "item":
                add(
                    parameter["id"],
                    "evolutions",
                    {
                        "source": reference,
                        "target": evolution["target"],
                        "method": evolution["method"]["name"],
                    },
                )

    for trainer in trainer_dataset["records"]:
        if not trainer["party"]:
            continue
        trainer_reference = {
            "trainer_id": trainer["trainer_id"],
            "name": trainer["name"],
            "class_name": trainer["class_name"],
        }
        for party_member in trainer["party"]:
            held_item = party_member.get("held_item")
            if held_item:
                add(
                    held_item["id"],
                    "trainer_held_by",
                    {**trainer_reference, "pokemon": party_member["pokemon"]},
                )
        reward_items = {
            reward_item["id"]: reward_item
            for reward_item in trainer.get("reward_items", [])
        }
        for reward_item in reward_items.values():
            add(reward_item["id"], "trainer_rewards", trainer_reference)

    for location in location_dataset["records"]:
        location_reference = {
            "header_id": location["header_id"],
            "name": location["name"],
            "internal_name": location["internal_name"],
        }
        for item in location.get("items", []):
            add(
                item["item_id"],
                "locations",
                {
                    **location_reference,
                    "kind": item["kind"],
                    "x": item["x"],
                    "z": item["z"],
                },
            )
        for shop in location.get("shops", []):
            for item in shop["items"]:
                add(
                    item["item_id"],
                    "shops",
                    {
                        **location_reference,
                        "kind": shop["kind"],
                        "currency": shop["currency"],
                        "price": item["price"],
                        "required_badges": item["required_badges"],
                    },
                )
        for gift in location.get("pokemon_gifts", []):
            if gift.get("held_item_id"):
                add(
                    gift["held_item_id"],
                    "gifts",
                    {
                        **location_reference,
                        "pokemon": {"id": gift["species_id"], "name": gift["name"]},
                    },
                )
        for trade in location.get("npc_trades", []):
            if trade.get("held_item_id"):
                add(
                    trade["held_item_id"],
                    "trades",
                    {
                        **location_reference,
                        "trade_id": trade["trade_id"],
                        "pokemon": {
                            "id": trade["offered_species_id"],
                            "name": trade["offered_species_name"],
                        },
                    },
                )

    records = []
    for source in item_dataset["records"]:
        if not source["public"]:
            continue
        item_id = source["item_id"]
        relation = relationships.get(item_id, {})
        records.append(
            {
                **source,
                "slug": pokedb.item_slug(source["name"]),
                "wild_held_by": relation.get("wild_held_by", []),
                "trainer_held_by": relation.get("trainer_held_by", []),
                "trainer_rewards": relation.get("trainer_rewards", []),
                "locations": relation.get("locations", []),
                "shops": relation.get("shops", []),
                "gifts": relation.get("gifts", []),
                "trades": relation.get("trades", []),
                "evolutions": relation.get("evolutions", []),
            }
        )
    slugs = [record["slug"] for record in records]
    if len(slugs) != len(set(slugs)):
        raise DataSourceError("ROM item names do not produce unique page slugs")
    return {
        "schema_version": 1,
        "game": game,
        "dataset": "items",
        "record_count": len(records),
        "referenced_record_count": sum(_item_is_referenced(record) for record in records),
        "source": item_dataset["source"],
        "supplemental_sources": {
            "pokemon": pokemon_dataset["source"],
            "trainers": trainer_dataset["source"],
            "locations": location_dataset["source"],
        },
        "records": records,
    }


def _item_is_referenced(record: dict[str, Any]) -> bool:
    return any(
        record[field]
        for field in (
            "wild_held_by",
            "trainer_held_by",
            "trainer_rewards",
            "locations",
            "shops",
            "gifts",
            "trades",
            "evolutions",
        )
    )

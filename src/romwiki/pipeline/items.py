from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from romwiki.engines.registry import get_engine
from romwiki.pipeline.identify import InspectionResult
from romwiki.pipeline.map_headers import read_code_binary
from romwiki.platforms.registry import get_platform
from romwiki.schema.versions import (
    ITEMS_ENRICHED_SCHEMA_VERSION,
    ITEMS_RAW_SCHEMA_VERSION,
)
from romwiki.sources import PokeDBGeneration
from romwiki.util.errors import DataSourceError, ProfileError
from romwiki.util.json_io import write_json_atomic
from romwiki.util.text import name_slug


def extract_item_dataset(result: InspectionResult) -> dict[str, Any]:
    if result.match is None:
        raise ProfileError("A known game profile is required for item extraction")
    profile = result.match.profile
    try:
        item_archive_path = profile.layout["item_data"]
        message_archive_path = profile.layout["messages"]
        item_names_member = profile.parameters["item_names_member"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} is missing item metadata: {error.args[0]}"
        ) from error
    berry_data_path = profile.layout.get("berry_data")
    type_names_member = profile.parameters.get("type_names_member")
    fossil_revival_table_offset = profile.parameters.get("fossil_revival_table_offset")
    fossil_revival_count = profile.parameters.get("fossil_revival_count")
    fossil_revival_script_file = profile.parameters.get("fossil_revival_script_file")
    first_berry_item_id = profile.parameters.get("first_berry_item_id")

    platform = get_platform(profile.platform)
    engine = get_engine(profile.engine).items
    filesystem = platform.filesystem_from_image(result.image)
    item_archive = platform.archive_cls.from_bytes(filesystem.read(item_archive_path))
    messages = platform.archive_cls.from_bytes(filesystem.read(message_archive_path))
    item_names = engine.parse_english_message_archive(messages.read(item_names_member))

    type_names: tuple[str, ...] = ()
    if type_names_member is not None:
        type_names = engine.parse_english_message_archive(
            messages.read(type_names_member)
        )
    else:
        # This generation has no ROM text table for type names at all (no
        # new types were added over Generation IV), so Natural Gift type
        # names fall back to the engine's own built-in constant table
        # instead of a ROM-decoded one.
        type_names = get_engine(profile.engine).enrich.TYPE_NAMES

    source: dict[str, Any] = {
        "rom_sha256": result.image.hashes.sha256,
        "archive": item_archive_path,
        "item_names": {
            "archive": message_archive_path,
            "member": item_names_member,
        },
    }

    if hasattr(engine, "find_item_archive_members"):
        arm9_data = read_code_binary(platform, result.image)
        map_offset, data_members = engine.find_item_archive_members(
            arm9_data,
            item_count=len(item_names),
            data_member_count=len(item_archive.members),
        )
        source["item_archive_map"] = {
            "source": "arm9",
            "offset": map_offset,
            "record_count": len(data_members),
        }
    else:
        arm9_data = None
        data_members = tuple(range(len(item_archive.members)))
        source["item_archive_map"] = {
            "source": "archive-index",
            "record_count": len(data_members),
        }

    if type_names_member is not None:
        source["type_names"] = {
            "archive": message_archive_path,
            "member": type_names_member,
        }

    revives_into_by_item: dict[int, int] = {}
    if fossil_revival_table_offset is not None:
        if arm9_data is None:
            arm9_data = read_code_binary(platform, result.image)
        fossil_revivals = engine.parse_fossil_revival_table(
            arm9_data,
            offset=fossil_revival_table_offset,
            count=fossil_revival_count,
            item_count=len(item_names),
            species_count=engine.POKEMON_NAME_COUNT,
        )
        revives_into_by_item = {
            revival.item_id: revival.species_id for revival in fossil_revivals
        }
        source["fossil_revival_table"] = {
            "source": "arm9",
            "offset": fossil_revival_table_offset,
            "record_count": len(fossil_revivals),
        }
    elif fossil_revival_script_file is not None:
        # Gen V has no fixed ARM9 table like Gen IV's -- the fossil
        # scientist's own script (`layout.scripts`) picks a species by
        # literally comparing the handed-over item against each real fossil
        # item ID (see gen5/bw/scripts.py's module docstring for the full
        # disassembly and cross-check against both real ROMs).
        scripts_path = profile.layout["scripts"]
        scripts_archive = platform.archive_cls.from_bytes(filesystem.read(scripts_path))
        fossil_revivals = engine.parse_fossil_revival_table(
            scripts_archive.read(fossil_revival_script_file)
        )
        revives_into_by_item = {
            revival.item_id: revival.species_id for revival in fossil_revivals
        }
        source["fossil_revival_table"] = {
            "source": "script",
            "archive": scripts_path,
            "member": fossil_revival_script_file,
            "record_count": len(fossil_revivals),
        }

    berry_by_item: dict[int, dict[str, Any]] = {}
    if berry_data_path is not None:
        berry_archive = platform.archive_cls.from_bytes(
            filesystem.read(berry_data_path)
        )
        for index in range(len(berry_archive.members)):
            berry = engine.parse_berry_record(berry_archive.read(index))
            berry_by_item[first_berry_item_id + index] = {
                **asdict(berry),
                "firmness_name": engine.BERRY_FIRMNESS_NAMES.get(berry.firmness),
            }
        source["berry_data"] = {
            "archive": berry_data_path,
            "record_count": len(berry_by_item),
        }

    # "???" is the ROM's own name-table sentinel for unused item text slots
    # (seen in Gen5, where item ID always equals its archive member, so
    # Gen4's "member 0 is unused" heuristic alone can't exclude them).
    records = []
    for item_id, data_member in enumerate(data_members):
        parsed = engine.parse_item_record(
            item_archive.read(data_member),
            item_id=item_id,
            data_archive_member=data_member,
            archive_path=item_archive_path,
        ).to_dict()
        name = item_names[item_id]
        record = {
            **parsed,
            "name": name,
            "public": item_id > 0 and data_member > 0 and name != "???",
            "revives_into_species_id": revives_into_by_item.get(item_id),
            "berry": berry_by_item.get(item_id),
        }

        if "field_pocket_id" in parsed:
            pocket_id = parsed["field_pocket_id"]
            if pocket_id >= len(engine.ITEM_POCKET_NAMES):
                raise DataSourceError(f"Unknown item pocket ID: {pocket_id}")
            record["pocket"] = {
                "id": pocket_id,
                "name": engine.ITEM_POCKET_NAMES[pocket_id],
            }

        if "field_use_function_id" in parsed:
            field_use_id = parsed["field_use_function_id"]
            if field_use_id >= len(engine.ITEM_FIELD_USE_NAMES):
                raise DataSourceError(
                    f"Unknown item field-use function ID: {field_use_id}"
                )
            record["field_use"] = {
                "id": field_use_id,
                "name": engine.ITEM_FIELD_USE_NAMES[field_use_id],
            }

        if "natural_gift_type_id" in parsed:
            natural_gift_type_id = parsed["natural_gift_type_id"]
            if (
                natural_gift_type_id != engine.NATURAL_GIFT_TYPE_NONE
                and natural_gift_type_id >= len(type_names)
            ):
                raise DataSourceError(
                    f"Unknown Natural Gift type ID: {natural_gift_type_id}"
                )
            record["natural_gift_type"] = (
                None
                if natural_gift_type_id == engine.NATURAL_GIFT_TYPE_NONE
                else {
                    "id": natural_gift_type_id,
                    "name": name_slug(type_names[natural_gift_type_id]),
                }
            )

        records.append(record)

    return {
        "schema_version": ITEMS_RAW_SCHEMA_VERSION,
        "game": profile.id,
        "dataset": "items_raw",
        "record_count": len(records),
        "public_record_count": sum(record["public"] for record in records),
        "source": source,
        "records": records,
    }


def write_item_dataset(dataset: dict[str, Any], output_path: Path) -> None:
    write_json_atomic(output_path, dataset)


def build_item_dataset(
    item_dataset: dict[str, Any],
    pokedb: PokeDBGeneration,
    pokemon_dataset: dict[str, Any],
    trainer_dataset: dict[str, Any] | None,
    location_dataset: dict[str, Any] | None,
    *,
    trade_dataset: dict[str, Any] | None = None,
    mart_dataset: dict[str, Any] | None = None,
    reference_version: str | None = None,
) -> dict[str, Any]:
    game = item_dataset.get("game")
    for label, dataset in (
        ("Pokémon", pokemon_dataset),
        ("trainer", trainer_dataset),
        ("location", location_dataset),
        ("trade", trade_dataset),
        ("mart", mart_dataset),
    ):
        if dataset is not None and dataset.get("game") != game:
            raise DataSourceError(
                f"Item and {label} datasets must be for the same game"
            )

    relationships: dict[int, dict[str, list[dict[str, Any]]]] = {}

    def add(item_id: int, kind: str, value: dict[str, Any]) -> None:
        if not item_id:
            return
        relationships.setdefault(item_id, {}).setdefault(kind, []).append(value)

    pokemon_by_species: dict[int, dict[str, Any]] = {}
    pokemon_by_slug: dict[str, dict[str, Any]] = {}
    for pokemon in pokemon_dataset["records"]:
        if not pokemon["public"]:
            continue
        reference = {
            "member": pokemon["member"],
            "national_dex_id": pokemon["national_dex_id"],
            "slug": pokemon["slug"],
            "name": pokemon["name"],
        }
        pokemon_by_slug[pokemon["slug"]] = reference
        if pokemon["national_dex_id"] is not None:
            pokemon_by_species.setdefault(pokemon["national_dex_id"], reference)
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

    for trainer in (trainer_dataset or {}).get("records", []):
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
        battle_items = {
            battle_item["id"]: battle_item
            for battle_item in trainer.get("ai_battle_items", [])
        }
        for battle_item in battle_items.values():
            add(battle_item["id"], "trainer_battle_items", trainer_reference)
        victory_item = trainer.get("victory_item")
        if victory_item:
            add(victory_item["id"], "trainer_rewards", trainer_reference)

    linked_shop_ids = set()
    for location in (location_dataset or {}).get("records", []):
        # Gen5 has no distinct internal debug-map name, so use its display
        # name for the shared relationship shape.
        location_reference = {
            "header_id": location["header_id"],
            "name": location["name"],
            "internal_name": location.get("internal_name", location["name"]),
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
            if not shop.get("dynamic"):
                linked_shop_ids.add(shop["inventory_id"])
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
                        "shop_id": shop["inventory_id"],
                        "shop_name": shop.get("name"),
                        "is_main_game": shop.get("is_main_game"),
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

    # Unlike Gen4's script-linked NPC trades above, Gen5's aren't attached to
    # a specific map header (see gen5/bw/__init__.py's module docstring), so
    # this is a flat pass over a standalone trade dataset instead of nested
    # inside the location loop.
    for trade in (trade_dataset or {}).get("records", []):
        held_item_id = trade.get("held_item_id")
        if not held_item_id:
            continue
        offered = None
        forme_id = trade.get("offered_forme_id")
        if forme_id:
            engine_tables = get_engine(pokemon_dataset["engine"]).enrich
            form_slug = engine_tables.TRAINER_FORM_SLUGS.get(
                (trade["offered_species_id"], forme_id)
            )
            if form_slug is not None:
                offered = pokemon_by_slug.get(form_slug)
        if offered is None:
            offered = pokemon_by_species.get(trade["offered_species_id"])
        pokemon_reference = (
            {"id": offered["member"], "name": offered["name"], "slug": offered["slug"]}
            if offered is not None
            else {"id": trade["offered_species_id"], "name": None}
        )
        add(
            held_item_id,
            "trades",
            {
                "trade_id": trade["trade_id"],
                "name": trade["ot_name"],
                "nickname": trade["nickname"],
                "ot_name": trade["ot_name"],
                "pokemon": pokemon_reference,
            },
        )

    # Preserve a flat fallback for any decoded inventory without a verified
    # location dispatcher.
    for shop in (mart_dataset or {}).get("records", []):
        if shop["shop_id"] in linked_shop_ids:
            continue
        for item in shop["items"]:
            add(
                item["item_id"],
                "shops",
                {
                    "shop_id": shop["shop_id"],
                    "shop_name": shop["name"],
                    "is_main_game": shop["is_main_game"],
                },
            )

    # ROM item names are usually unique, but not always: e.g. Gen5's real,
    # distinct male- and female-color Xtransceiver items share the exact
    # displayed name "Xtransceiver". Disambiguate with the item ID (a stable
    # ROM fact) rather than rejecting the whole dataset over a real game
    # design choice.
    slug_counts: dict[str, int] = {}
    for source in item_dataset["records"]:
        if source["public"]:
            page_slug = pokedb.item_slug(source["name"])
            slug_counts[page_slug] = slug_counts.get(page_slug, 0) + 1

    records = []
    for source in item_dataset["records"]:
        if not source["public"]:
            continue
        item_id = source["item_id"]
        relation = relationships.get(item_id, {})
        page_slug = pokedb.item_slug(source["name"])
        reference_slug = pokedb.item_reference_slug(source["name"])
        slug = f"{page_slug}-{item_id}" if slug_counts[page_slug] > 1 else page_slug
        records.append(
            {
                **source,
                "slug": slug,
                "reference": pokedb.item_reference(reference_slug, reference_version),
                "wild_held_by": relation.get("wild_held_by", []),
                "trainer_held_by": relation.get("trainer_held_by", []),
                "trainer_battle_items": relation.get("trainer_battle_items", []),
                "trainer_rewards": relation.get("trainer_rewards", []),
                "locations": relation.get("locations", []),
                "shops": relation.get("shops", []),
                "gifts": relation.get("gifts", []),
                "trades": relation.get("trades", []),
                "evolutions": relation.get("evolutions", []),
                "revives_into": pokemon_by_species.get(
                    source.get("revives_into_species_id")
                ),
            }
        )
    slugs = [record["slug"] for record in records]
    if len(slugs) != len(set(slugs)):
        raise DataSourceError("ROM item names do not produce unique page slugs")
    return {
        "schema_version": ITEMS_ENRICHED_SCHEMA_VERSION,
        "game": game,
        "dataset": "items",
        "record_count": len(records),
        "referenced_record_count": sum(
            _item_is_referenced(record) for record in records
        ),
        "source": item_dataset["source"],
        "supplemental_sources": {
            "pokemon": pokemon_dataset["source"],
            "trainers": trainer_dataset["source"] if trainer_dataset else None,
            "locations": location_dataset["source"] if location_dataset else None,
            "trades": trade_dataset["source"] if trade_dataset else None,
            "marts": mart_dataset["source"] if mart_dataset else None,
        },
        "records": records,
    }


def _item_is_referenced(record: dict[str, Any]) -> bool:
    return any(
        record[field]
        for field in (
            "wild_held_by",
            "trainer_held_by",
            "trainer_battle_items",
            "trainer_rewards",
            "locations",
            "shops",
            "gifts",
            "trades",
            "evolutions",
        )
    ) or bool(record["revives_into"])

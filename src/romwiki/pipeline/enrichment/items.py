from __future__ import annotations

from collections import defaultdict
from typing import Any

from romwiki.engines.registry import get_engine
from romwiki.schema.versions import ITEMS_ENRICHED_SCHEMA_VERSION
from romwiki.sources import PokeDBGeneration
from romwiki.util.errors import DataSourceError

ItemRelationships = dict[int, dict[str, list[dict[str, Any]]]]


def _add_relationship(
    relationships: ItemRelationships,
    item_id: int,
    kind: str,
    value: dict[str, Any],
) -> None:
    if item_id:
        relationships.setdefault(item_id, {}).setdefault(kind, []).append(value)


def _merge_relationships(target: ItemRelationships, source: ItemRelationships) -> None:
    for item_id, relationships in source.items():
        for kind, values in relationships.items():
            target.setdefault(item_id, {}).setdefault(kind, []).extend(values)


def _collect_pokemon_relationships(
    pokemon_dataset: dict[str, Any],
) -> tuple[
    ItemRelationships,
    dict[int, dict[str, Any]],
    dict[str, dict[str, Any]],
]:
    relationships: ItemRelationships = {}
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
            _add_relationship(
                relationships,
                held_item["id"],
                "wild_held_by",
                {**reference, "rarity": held_item["rarity"]},
            )
        for evolution in pokemon.get("evolutions", []):
            parameter = evolution.get("parameter_data")
            if parameter and parameter.get("kind") == "item":
                _add_relationship(
                    relationships,
                    parameter["id"],
                    "evolutions",
                    {
                        "source": reference,
                        "target": evolution["target"],
                        "method": evolution["method"]["name"],
                    },
                )
    return relationships, pokemon_by_species, pokemon_by_slug


def _collect_trainer_relationships(
    trainer_dataset: dict[str, Any] | None,
) -> ItemRelationships:
    relationships: ItemRelationships = {}
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
                _add_relationship(
                    relationships,
                    held_item["id"],
                    "trainer_held_by",
                    {**trainer_reference, "pokemon": party_member["pokemon"]},
                )
        battle_items = {
            battle_item["id"]: battle_item
            for battle_item in trainer.get("ai_battle_items", [])
        }
        for battle_item in battle_items.values():
            _add_relationship(
                relationships,
                battle_item["id"],
                "trainer_battle_items",
                trainer_reference,
            )
        victory_item = trainer.get("victory_item")
        if victory_item:
            _add_relationship(
                relationships,
                victory_item["id"],
                "trainer_rewards",
                trainer_reference,
            )
    return relationships


def _collect_location_relationships(
    item_dataset: dict[str, Any],
    location_dataset: dict[str, Any] | None,
) -> tuple[ItemRelationships, set[int], set[int], dict[int, list[dict[str, Any]]]]:
    relationships: ItemRelationships = {}
    linked_shop_ids: set[int] = set()
    linked_trade_ids: set[int] = set()
    fossil_locations_by_species: dict[int, list[dict[str, Any]]] = defaultdict(list)
    fossil_source = item_dataset.get("source", {}).get("fossil_revival_table")
    fossil_member = (
        fossil_source.get("member") if isinstance(fossil_source, dict) else None
    )
    for location in (location_dataset or {}).get("records", []):
        location_reference = {
            "header_id": location["header_id"],
            "name": location["name"],
            "section_name": location.get("section_name"),
            "internal_name": location.get("internal_name", location["name"]),
        }
        for item in location.get("items", []):
            _add_relationship(
                relationships,
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
            if not shop.get("dynamic") and shop.get("inventory_id") is not None:
                linked_shop_ids.add(shop["inventory_id"])
            for item in shop["items"]:
                _add_relationship(
                    relationships,
                    item["item_id"],
                    "shops",
                    {
                        **location_reference,
                        "kind": shop["kind"],
                        "currency": shop["currency"],
                        "price": item["price"],
                        "required_badges": item["required_badges"],
                        "shop_id": shop["inventory_id"],
                        "selector_id": shop.get("selector_id"),
                        "selector_ids": shop.get("selector_ids", []),
                        "vendor_id": shop.get("vendor_id"),
                        "shop_name": shop.get("name"),
                        "is_main_game": shop.get("is_main_game"),
                        "availability": (
                            item.get("availability") or shop.get("availability")
                        ),
                    },
                )
        for gift in location.get("pokemon_gifts", []):
            if gift.get("held_item_id"):
                _add_relationship(
                    relationships,
                    gift["held_item_id"],
                    "gifts",
                    {
                        **location_reference,
                        "pokemon": {"id": gift["species_id"], "name": gift["name"]},
                    },
                )
        for trade in location.get("npc_trades", []):
            linked_trade_ids.add(trade["trade_id"])
            if trade.get("held_item_id"):
                _add_relationship(
                    relationships,
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
        if isinstance(fossil_member, int):
            for encounter in location.get("static_encounters", []):
                if encounter.get("script_file_id") != fossil_member:
                    continue
                reference = {
                    "header_id": location["header_id"],
                    "name": location["name"],
                    "internal_name": location.get("internal_name", location["name"]),
                }
                locations = fossil_locations_by_species[encounter["species_id"]]
                if reference not in locations:
                    locations.append(reference)
    return (
        relationships,
        linked_shop_ids,
        linked_trade_ids,
        fossil_locations_by_species,
    )


def _collect_detached_trade_relationships(
    trade_dataset: dict[str, Any] | None,
    pokemon_dataset: dict[str, Any],
    pokemon_by_species: dict[int, dict[str, Any]],
    pokemon_by_slug: dict[str, dict[str, Any]],
    linked_trade_ids: set[int],
) -> ItemRelationships:
    relationships: ItemRelationships = {}
    for trade in (trade_dataset or {}).get("records", []):
        if trade["trade_id"] in linked_trade_ids:
            continue
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
        _add_relationship(
            relationships,
            held_item_id,
            "trades",
            {
                "trade_id": trade["trade_id"],
                "name": trade["ot_name"],
                "nickname": trade["nickname"],
                "ot_name": trade["ot_name"],
                "interaction": trade.get("interaction", "fixed-location"),
                "pokemon": pokemon_reference,
            },
        )
    return relationships


def _collect_mart_relationships(
    mart_dataset: dict[str, Any] | None, linked_shop_ids: set[int]
) -> ItemRelationships:
    relationships: ItemRelationships = {}
    for shop in (mart_dataset or {}).get("records", []):
        if shop["shop_id"] in linked_shop_ids:
            continue
        for item in shop["items"]:
            _add_relationship(
                relationships,
                item["item_id"],
                "shops",
                {
                    "shop_id": shop["shop_id"],
                    "shop_name": shop["name"],
                    "is_main_game": shop["is_main_game"],
                },
            )
    return relationships


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
        ("PokÃ©mon", pokemon_dataset),
        ("trainer", trainer_dataset),
        ("location", location_dataset),
        ("trade", trade_dataset),
        ("mart", mart_dataset),
    ):
        if dataset is not None and dataset.get("game") != game:
            raise DataSourceError(
                f"Item and {label} datasets must be for the same game"
            )

    pokemon_relationships, pokemon_by_species, pokemon_by_slug = (
        _collect_pokemon_relationships(pokemon_dataset)
    )
    trainer_relationships = _collect_trainer_relationships(trainer_dataset)
    (
        location_relationships,
        linked_shop_ids,
        linked_trade_ids,
        fossil_locations_by_species,
    ) = _collect_location_relationships(item_dataset, location_dataset)
    trade_relationships = _collect_detached_trade_relationships(
        trade_dataset,
        pokemon_dataset,
        pokemon_by_species,
        pokemon_by_slug,
        linked_trade_ids,
    )
    mart_relationships = _collect_mart_relationships(mart_dataset, linked_shop_ids)

    relationships: ItemRelationships = {}
    for collected in (
        pokemon_relationships,
        trainer_relationships,
        location_relationships,
        trade_relationships,
        mart_relationships,
    ):
        _merge_relationships(relationships, collected)

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
                "revives_at": fossil_locations_by_species.get(
                    source.get("revives_into_species_id"), []
                ),
            }
        )
    slugs = [record["slug"] for record in records]
    if len(slugs) != len(set(slugs)):
        raise DataSourceError("ROM item names do not produce unique page slugs")
    return {
        "schema_version": ITEMS_ENRICHED_SCHEMA_VERSION,
        "game": game,
        "engine": item_dataset.get("engine", pokemon_dataset.get("engine", "unknown")),
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

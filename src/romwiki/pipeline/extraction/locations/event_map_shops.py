from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from romwiki.engines.concerns import LocationConcern
from romwiki.schema import LocationShop, LocationShopItem
from romwiki.util.errors import InvalidRomError, ProfileError


@dataclass(frozen=True)
class EventMapShopCatalogs:
    item_names: tuple[str, ...]
    decoration_names: tuple[str, ...]
    seal_names: tuple[str, ...]
    common_items: tuple[Any, ...]
    specialty_inventories: tuple[tuple[int, ...], ...]
    decoration_inventory_start: int
    decoration_inventory_count: int
    seal_inventory_start: int
    seal_inventory_count: int
    frontier_inventory_count: int
    item_prices: tuple[int, ...]
    decoration_prices: tuple[int, ...]
    seal_prices: tuple[int, ...]
    frontier_prices: dict[int, int]


@dataclass(frozen=True)
class EventMapShopSource:
    catalogs: EventMapShopCatalogs
    decoration_names_metadata: dict[str, Any] | None
    seal_names_metadata: dict[str, Any] | None
    shops_metadata: dict[str, Any]


@dataclass(frozen=True)
class _MartInventory:
    names: tuple[str, ...]
    source_items: tuple[tuple[int, Any], ...]
    prices: tuple[int, ...] | None
    price_by_item: dict[int, int] | None
    currency: str


@dataclass(frozen=True)
class _ShopParameters:
    common_inventory_offset: int
    specialty_pointer_table_offset: int
    specialty_inventory_count: int
    decoration_names_member: int | None
    decoration_name_count: int
    decoration_price_table_offset: int | None
    decoration_inventory_start: int
    decoration_inventory_count: int
    seal_names_member: int | None
    seal_price_table_offset: int | None
    seal_inventory_start: int
    seal_inventory_count: int
    frontier_inventory_count: int
    frontier_price_overlay_id: int | None
    frontier_price_table_offset: int | None
    frontier_price_record_count: int


def _read_shop_parameters(profile: Any) -> _ShopParameters:
    parameters = profile.parameters
    try:
        common_inventory_offset = parameters["common_mart_inventory_offset"]
        specialty_pointer_table_offset = parameters[
            "specialty_mart_pointer_table_offset"
        ]
        specialty_inventory_count = parameters["specialty_mart_inventory_count"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} is missing location metadata: {error.args[0]}"
        ) from error
    # Decorations, seals, and the Battle Frontier were never in
    # Diamond/Pearl, so these catalogs are optional per profile/engine and a
    # profile can omit them entirely instead of crashing.
    return _ShopParameters(
        common_inventory_offset=common_inventory_offset,
        specialty_pointer_table_offset=specialty_pointer_table_offset,
        specialty_inventory_count=specialty_inventory_count,
        decoration_names_member=profile.optional_int_parameter(
            "decoration_names_member"
        ),
        decoration_name_count=profile.int_parameter("decoration_name_count", 0),
        decoration_price_table_offset=profile.optional_int_parameter(
            "decoration_price_table_offset"
        ),
        decoration_inventory_start=profile.int_parameter(
            "decoration_mart_inventory_start", 0
        ),
        decoration_inventory_count=profile.int_parameter(
            "decoration_mart_inventory_count", 0
        ),
        seal_names_member=profile.optional_int_parameter("seal_names_member"),
        seal_price_table_offset=profile.optional_int_parameter(
            "seal_price_table_offset"
        ),
        seal_inventory_start=profile.int_parameter("seal_mart_inventory_start", 0),
        seal_inventory_count=profile.int_parameter("seal_mart_inventory_count", 0),
        frontier_inventory_count=profile.int_parameter(
            "frontier_mart_inventory_count", 0
        ),
        frontier_price_overlay_id=profile.optional_int_parameter(
            "frontier_price_overlay_id"
        ),
        frontier_price_table_offset=profile.optional_int_parameter(
            "frontier_price_table_offset"
        ),
        frontier_price_record_count=profile.int_parameter(
            "frontier_price_record_count", 0
        ),
    )


def load_event_map_shop_source(
    profile: Any,
    engine: LocationConcern,
    platform: Any,
    image: Any,
    *,
    filesystem: Any,
    arm9_data: bytes,
    arm9_load_address: int,
    messages: Any,
    item_names: tuple[str, ...],
    item_data_path: str,
    scripts_path: str,
    messages_path: str,
) -> EventMapShopSource:
    parameters = _read_shop_parameters(profile)
    decoration_names, decoration_prices = _decode_decorations(
        engine, messages, arm9_data, parameters
    )
    seal_names, seal_prices = _decode_seals(engine, messages, arm9_data, parameters)
    frontier_prices = _decode_frontier_prices(
        profile, engine, platform, image, parameters
    )
    item_archive_map_offset, item_prices = _decode_item_prices(
        engine, platform, filesystem, arm9_data, item_data_path, item_names
    )
    catalogs = EventMapShopCatalogs(
        item_names=item_names,
        decoration_names=decoration_names,
        seal_names=seal_names,
        common_items=engine.parse_common_mart_inventory(
            arm9_data,
            offset=parameters.common_inventory_offset,
            item_count=len(item_names),
        ),
        specialty_inventories=engine.parse_specialty_mart_inventories(
            arm9_data,
            pointer_table_offset=parameters.specialty_pointer_table_offset,
            inventory_count=parameters.specialty_inventory_count,
            load_address=arm9_load_address,
            item_count=len(item_names),
        ),
        decoration_inventory_start=parameters.decoration_inventory_start,
        decoration_inventory_count=parameters.decoration_inventory_count,
        seal_inventory_start=parameters.seal_inventory_start,
        seal_inventory_count=parameters.seal_inventory_count,
        frontier_inventory_count=parameters.frontier_inventory_count,
        item_prices=item_prices,
        decoration_prices=decoration_prices,
        seal_prices=seal_prices,
        frontier_prices=frontier_prices,
    )
    return EventMapShopSource(
        catalogs=catalogs,
        decoration_names_metadata=(
            {
                "archive": messages_path,
                "member": parameters.decoration_names_member,
                "count": parameters.decoration_name_count,
            }
            if parameters.decoration_names_member is not None
            else None
        ),
        seal_names_metadata=(
            {"archive": messages_path, "member": parameters.seal_names_member}
            if parameters.seal_names_member is not None
            else None
        ),
        shops_metadata=_build_shops_metadata(
            parameters,
            scripts_path=scripts_path,
            item_data_path=item_data_path,
            item_archive_map_offset=item_archive_map_offset,
        ),
    )


def _build_shops_metadata(
    parameters: _ShopParameters,
    *,
    scripts_path: str,
    item_data_path: str,
    item_archive_map_offset: int,
) -> dict[str, Any]:
    return {
        "scripts_archive": scripts_path,
        "item_data_archive": item_data_path,
        "item_archive_map_arm9_offset": item_archive_map_offset,
        "common_inventory_arm9_offset": parameters.common_inventory_offset,
        "specialty_pointer_table_arm9_offset": (
            parameters.specialty_pointer_table_offset
        ),
        "decoration_price_table_arm9_offset": parameters.decoration_price_table_offset,
        "seal_price_table_arm9_offset": parameters.seal_price_table_offset,
        "frontier_price_table": (
            {
                "overlay_id": parameters.frontier_price_overlay_id,
                "offset": parameters.frontier_price_table_offset,
                "record_count": parameters.frontier_price_record_count,
            }
            if parameters.frontier_price_overlay_id is not None
            else None
        ),
    }


def _decode_decorations(
    engine: LocationConcern,
    messages: Any,
    arm9_data: bytes,
    parameters: _ShopParameters,
) -> tuple[tuple[str, ...], tuple[int, ...]]:
    if parameters.decoration_names_member is None:
        return (), ()
    decoration_names = engine.parse_english_message_archive(
        messages.read(parameters.decoration_names_member),
        limit=parameters.decoration_name_count,
    )
    return decoration_names, engine.parse_decoration_price_table(
        arm9_data,
        offset=parameters.decoration_price_table_offset,
        decoration_count=len(decoration_names),
    )


def _decode_seals(
    engine: LocationConcern,
    messages: Any,
    arm9_data: bytes,
    parameters: _ShopParameters,
) -> tuple[tuple[str, ...], tuple[int, ...]]:
    if parameters.seal_names_member is None:
        return (), ()
    seal_names = engine.parse_english_message_archive(
        messages.read(parameters.seal_names_member)
    )
    return seal_names, engine.parse_seal_price_table(
        arm9_data,
        offset=parameters.seal_price_table_offset,
        seal_count=len(seal_names),
    )


def _decode_frontier_prices(
    profile: Any,
    engine: LocationConcern,
    platform: Any,
    image: Any,
    parameters: _ShopParameters,
) -> dict[int, int]:
    if parameters.frontier_price_overlay_id is None:
        return {}
    if platform.read_overlay is None:
        raise ProfileError(f"Platform {profile.platform!r} does not support overlays")
    _, frontier_overlay = platform.read_overlay(
        image, parameters.frontier_price_overlay_id
    )
    return engine.parse_frontier_price_table(
        frontier_overlay,
        offset=parameters.frontier_price_table_offset,
        record_count=parameters.frontier_price_record_count,
    )


def _decode_item_prices(
    engine: LocationConcern,
    platform: Any,
    filesystem: Any,
    arm9_data: bytes,
    item_data_path: str,
    item_names: tuple[str, ...],
) -> tuple[int, tuple[int, ...]]:
    item_data = platform.archive_cls.from_bytes(filesystem.read(item_data_path))
    item_archive_map_offset, item_data_members = engine.find_item_archive_members(
        arm9_data,
        item_count=len(item_names),
        data_member_count=len(item_data.members),
    )
    return item_archive_map_offset, tuple(
        engine.parse_item_price(item_data.read(data_member))
        for data_member in item_data_members
    )


def extract_event_map_location_shops(
    engine: LocationConcern,
    script: bytes,
    *,
    script_file_id: int,
    catalogs: EventMapShopCatalogs,
) -> tuple[LocationShop, ...]:
    shops = []
    for command in engine.parse_mart_commands(script):
        inventory = _resolve_mart_inventory(command, catalogs, script_file_id)
        for item_id, _required_badges in inventory.source_items:
            if not 0 < item_id < len(inventory.names):
                raise InvalidRomError(
                    f"Script {script_file_id} {command.kind} mart references "
                    f"missing catalog entry {item_id}"
                )
            if (
                inventory.price_by_item is not None
                and item_id not in inventory.price_by_item
            ):
                raise InvalidRomError(
                    f"Script {script_file_id} Battle Frontier mart item {item_id} "
                    "has no BP price"
                )
        shops.append(
            LocationShop(
                kind=command.kind,
                currency=inventory.currency,
                inventory_id=command.inventory_id,
                script_file_id=script_file_id,
                command_offset=command.offset,
                items=tuple(
                    LocationShopItem(
                        item_id=item_id,
                        name=inventory.names[item_id],
                        price=_shop_item_price(inventory, item_id),
                        required_badges=required_badges,
                    )
                    for item_id, required_badges in inventory.source_items
                ),
                schedule=engine.shop_schedule_label(command.kind, command.inventory_id),
            )
        )
    return tuple(shops)


def _shop_item_price(inventory: _MartInventory, item_id: int) -> int | None:
    if inventory.price_by_item is not None:
        return inventory.price_by_item[item_id]
    if inventory.prices is not None and item_id < len(inventory.prices):
        return inventory.prices[item_id]
    return None


def _resolve_mart_inventory(
    command: Any, catalogs: EventMapShopCatalogs, script_file_id: int
) -> _MartInventory:
    if command.kind == "common":
        return _MartInventory(
            names=catalogs.item_names,
            source_items=tuple(
                (item.item_id, item.required_badges) for item in catalogs.common_items
            ),
            prices=catalogs.item_prices,
            price_by_item=None,
            currency="money",
        )
    inventory_index = command.inventory_id
    names = catalogs.item_names
    prices: tuple[int, ...] | None = catalogs.item_prices
    price_by_item: dict[int, int] | None = None
    currency = "money"
    if command.kind == "decoration":
        _check_mart_inventory_id(
            command, catalogs.decoration_inventory_count, script_file_id, "decoration"
        )
        inventory_index += catalogs.decoration_inventory_start
        names = catalogs.decoration_names
        prices = catalogs.decoration_prices
    elif command.kind == "seal":
        _check_mart_inventory_id(
            command, catalogs.seal_inventory_count, script_file_id, "seal"
        )
        inventory_index += catalogs.seal_inventory_start
        names = catalogs.seal_names
        prices = catalogs.seal_prices
    elif command.kind == "frontier":
        _check_mart_inventory_id(
            command,
            catalogs.frontier_inventory_count,
            script_file_id,
            "Battle Frontier",
        )
        prices = None
        price_by_item = catalogs.frontier_prices
        currency = "bp"
    if inventory_index >= len(catalogs.specialty_inventories):
        raise InvalidRomError(
            f"Script {script_file_id} references missing {command.kind} mart "
            f"inventory {inventory_index}"
        )
    return _MartInventory(
        names=names,
        source_items=tuple(
            (item_id, None)
            for item_id in catalogs.specialty_inventories[inventory_index]
        ),
        prices=prices,
        price_by_item=price_by_item,
        currency=currency,
    )


def _check_mart_inventory_id(
    command: Any, inventory_count: int, script_file_id: int, label: str
) -> None:
    if command.inventory_id >= inventory_count:
        raise InvalidRomError(
            f"Script {script_file_id} references missing {label} mart "
            f"{command.inventory_id}"
        )

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class LocationWarp:
    index: int
    x: int
    z: int
    destination_header_id: int | None
    destination_warp_id: int | None
    destination_name: str | None
    destination_internal_name: str | None
    destination_warp_exists: bool | None
    dynamic: bool


@dataclass(frozen=True, slots=True)
class LocationConnection:
    destination_header_id: int
    destination_name: str
    destination_internal_name: str
    directions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LocationTrainerReference:
    trainer_id: int
    name: str
    class_name: str
    source: str


@dataclass(frozen=True, slots=True)
class LocationItem:
    item_id: int
    name: str
    kind: str
    event_index: int
    x: int
    z: int
    y: int
    hidden_flag: int | None


@dataclass(frozen=True, slots=True)
class LocationShopItem:
    item_id: int
    name: str
    price: int | None
    required_badges: int | None


@dataclass(frozen=True, slots=True)
class LocationShop:
    kind: str
    currency: str
    inventory_id: int
    script_file_id: int
    command_offset: int
    items: tuple[LocationShopItem, ...]


@dataclass(frozen=True, slots=True)
class LocationPokemonGift:
    kind: str
    species_id: int
    name: str
    level: int
    held_item_id: int | None
    held_item_name: str | None
    script_file_id: int
    command_offset: int


@dataclass(frozen=True, slots=True)
class LocationStaticEncounter:
    species_id: int
    name: str
    level: int
    command: str
    script_file_id: int
    command_offset: int


@dataclass(frozen=True, slots=True)
class LocationNpcTrade:
    trade_id: int
    requested_species_id: int
    requested_species_name: str
    offered_species_id: int
    offered_species_name: str
    nickname: str
    ivs: tuple[int, ...]
    nature: str
    held_item_id: int | None
    held_item_name: str | None
    ot_name: str
    ot_id: int
    ot_gender: str
    language: str
    personality: int
    script_file_id: int
    command_offset: int


@dataclass(frozen=True, slots=True)
class Gen4Location:
    header_id: int
    internal_name: str
    location_name_id: int
    name: str
    matrix_id: int
    event_file_id: int | None
    encounter_id: int | None
    warps: tuple[LocationWarp, ...]
    connections: tuple[LocationConnection, ...]
    trainers: tuple[LocationTrainerReference, ...]
    items: tuple[LocationItem, ...]
    shops: tuple[LocationShop, ...]
    pokemon_gifts: tuple[LocationPokemonGift, ...]
    static_encounters: tuple[LocationStaticEncounter, ...]
    npc_trades: tuple[LocationNpcTrade, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

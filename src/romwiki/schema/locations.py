from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from romwiki.schema.pokemon import RecordProvenance


@dataclass(frozen=True, slots=True)
class LocationWarp:
    index: int
    x: int
    z: int
    destination_header_id: int | None
    destination_warp_id: int | None
    destination_name: str | None
    destination_section_name: str | None
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
    class_name: str | None
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
class LocationScriptAwardedItem:
    item_id: int
    name: str
    quantity: int
    script_file_id: int
    command_offset: int
    command: str


@dataclass(frozen=True, slots=True)
class LocationShopItem:
    item_id: int
    name: str
    price: int | None
    required_badges: int | None
    availability: str | None = None


@dataclass(frozen=True, slots=True)
class LocationShop:
    kind: str
    currency: str
    inventory_id: int | None
    script_file_id: int
    command_offset: int
    items: tuple[LocationShopItem, ...]
    schedule: str | None = None
    name: str | None = None
    is_main_game: bool | None = None
    selector_id: int | None = None
    mode: int | None = None
    dynamic: bool = False
    inventory_source: str = "catalog"
    availability: str | None = None
    vendor_id: str | None = None
    selector_ids: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class LocationMartReference:
    """A decoded mart-opening dispatch command with no decoded inventory.

    Distinct from `LocationShop`: this records that a real, verified
    mart-dispatch command exists and which map header owns it, without
    claiming to know what it sells. Used when the dispatch command itself is
    decodable but the inventory-content table it references is not (see
    `gen4/hgss/marts.py`'s module comment for why) -- publishing this
    location fact without item contents rather than not publishing it at
    all, since the location itself is real and verified.
    """

    kind: str
    inventory_id: int | None
    script_file_id: int
    command_offset: int


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
    level: int | None
    is_egg: bool
    command: str
    script_file_id: int
    command_offset: int


@dataclass(frozen=True, slots=True)
class LocationRoamingActivation:
    slot: int
    species_id: int
    species_name: str
    script_file_id: int
    command_offset: int


@dataclass(frozen=True, slots=True)
class BonusEncounterSpecies:
    species_id: int
    name: str


@dataclass(frozen=True, slots=True)
class LocationHoneyTree:
    common: tuple[BonusEncounterSpecies, ...]
    uncommon: tuple[BonusEncounterSpecies, ...]
    rare: tuple[BonusEncounterSpecies, ...]


@dataclass(frozen=True, slots=True)
class LocationDailyEncounterPool:
    kind: str
    species: tuple[BonusEncounterSpecies, ...]
    pre_national_dex_species: tuple[BonusEncounterSpecies, ...] | None


@dataclass(frozen=True, slots=True)
class LocationGameCornerPrize:
    item_id: int
    name: str
    price: int


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
    contest_stats: tuple[int, ...]
    unused_values: tuple[int, ...]
    script_file_id: int
    command_offset: int


@dataclass(frozen=True, slots=True)
class EventMapLocation:
    header_id: int
    internal_name: str
    location_name_id: int
    name: str
    matrix_id: int
    area_data_id: int
    level_script_id: int
    text_archive_id: int
    day_music_id: int
    night_music_id: int
    weather_id: int
    camera_id: int
    map_flags: int
    event_file_id: int | None
    encounter_id: int | None
    warps: tuple[LocationWarp, ...]
    connections: tuple[LocationConnection, ...]
    trainers: tuple[LocationTrainerReference, ...]
    items: tuple[LocationItem, ...]
    shops: tuple[LocationShop, ...]
    pokemon_gifts: tuple[LocationPokemonGift, ...]
    static_encounters: tuple[LocationStaticEncounter, ...]
    roaming_activations: tuple[LocationRoamingActivation, ...]
    npc_trades: tuple[LocationNpcTrade, ...]
    script_awarded_items: tuple[LocationScriptAwardedItem, ...]
    honey_tree: LocationHoneyTree | None
    daily_encounter_pool: LocationDailyEncounterPool | None
    game_corner_prizes: tuple[LocationGameCornerPrize, ...]
    provenance: RecordProvenance
    section_name: str | None = None
    section_name_source: dict[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class EncounterMapLocation:
    header_id: int
    name: str
    # The `WildPokemon` archive member (Wild Encounters' `map_index`) this
    # header's wild encounters come from, or None if this header has none.
    # Not resolved to a specific encounter-area page URL here since a single
    # map index can expand to up to 4 seasonal areas -- see data-sources.md.
    encounter_map_index: int | None
    # The `layout.map_matrices` (`a/0/0/9`) member this header's own outdoor-
    # connection grid comes from -- see `gen5/bw/locations.py`'s
    # `_MATRIX_ID_OFFSET` docstring for how this was found and verified.
    matrix_id: int
    provenance: RecordProvenance
    # The archive member containing this header's overworld objects. This is
    # identical to the header ID in BW, but is independently indexed in B2W2.
    overworld_file_id: int | None = None
    internal_name: str | None = None
    section_name: str | None = None
    section_name_source: dict[str, str] | None = None
    trainers: tuple[LocationTrainerReference, ...] = ()
    warps: tuple[LocationWarp, ...] = ()
    static_encounters: tuple[LocationStaticEncounter, ...] = ()
    pokemon_gifts: tuple[LocationPokemonGift, ...] = ()
    connections: tuple[LocationConnection, ...] = ()
    items: tuple[LocationItem, ...] = ()
    script_awarded_items: tuple[LocationScriptAwardedItem, ...] = ()
    shops: tuple[LocationShop, ...] = ()
    mart_references: tuple[LocationMartReference, ...] = ()
    npc_trades: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

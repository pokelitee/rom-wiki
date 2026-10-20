from __future__ import annotations

import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.pipeline.extraction.locations.arm9_event_map import (
    extract_arm9_event_map_location_dataset,
)
from romwiki.profiles.models import GameProfile, HashMatch, KnownHash
from romwiki.util.errors import InvalidRomError, ProfileError

_MODULE = "romwiki.pipeline.extraction.locations.arm9_event_map_source"

_NULL = 65535


class _Archive:
    """Minimal stand-in for the platform archive container."""

    def __init__(self, member_count: int, reader=None) -> None:
        self.members = tuple(range(member_count))
        self._reader = reader or (lambda index: b"")

    def read(self, index: int) -> bytes:
        return self._reader(index)


class _Engine:
    """A gen4-dppt-shaped locations engine stub the module can call."""

    ARCHIVE_MEMBER_NONE = _NULL
    DYNAMIC_WARP_HEADER_ID = -1
    DYNAMIC_WARP_ID = -1
    MATRIX_VOID_HEADER_IDS = ()
    ROAMING_SLOT_COUNT = 2
    ROAMING_SLOT_SPECIES_IDS = {0: 1, 1: 0}
    MAP_HEADER_SIZE = 1
    HONEY_TREE_HEADER_IDS = ()
    GREAT_MARSH_HEADER_IDS = ()
    TROPHY_GARDEN_HEADER_ID = None
    GAME_CORNER_PRIZE_EXCHANGE_HEADER_ID = None

    def __init__(self, *, headers, message_archives):
        self._headers = headers
        self.message_archives = message_archives
        self.events_by_id: dict[int, SimpleNamespace] = {}
        self.matrices_by_id: dict[int, SimpleNamespace] = {}
        self.common_mart_items: tuple = ()
        self.specialty_mart_inventories: tuple = ()
        self.item_data_members: tuple = ()
        self.item_prices_by_member: dict[bytes, int] = {}
        self.roaming_commands_by_script: dict[int, tuple] = {}
        self.mart_commands_by_script: dict[int, tuple] = {}
        self.gift_commands_by_script: dict[int, tuple] = {}
        self.egg_commands_by_script: dict[int, tuple] = {}
        self.static_commands_by_script: dict[int, tuple] = {}
        self.trade_commands_by_script: dict[int, tuple] = {}
        self.npc_trade_records: tuple = ()

    # -- headers / names -------------------------------------------------
    def parse_map_headers(self, header_data, map_names_data, count):
        return self._headers

    def parse_english_message_archive(self, data, limit=None):
        names = self.message_archives[data]
        return names[:limit] if limit is not None else names

    # -- events / matrices -------------------------------------------------
    def parse_map_events(self, data, event_file_id):
        return self.events_by_id[event_file_id]

    def parse_map_matrix(self, data, matrix_id):
        return self.matrices_by_id.get(matrix_id, SimpleNamespace(header_ids=None))

    def find_script_awarded_items(self, data, *, item_count):
        return ()

    def is_visible_item_candidate(self, event):
        return False

    def is_hidden_item_candidate(self, event):
        return False

    def resolve_visible_item_id(self, event, item_count):
        return getattr(event, "visible_item_id", None)

    def resolve_hidden_item_id(self, event, item_count):
        return getattr(event, "hidden_item_id", None)

    # -- marts -------------------------------------------------------------
    def parse_common_mart_inventory(self, arm9_data, *, offset, item_count):
        return self.common_mart_items

    def parse_specialty_mart_inventories(
        self,
        arm9_data,
        *,
        pointer_table_offset,
        inventory_count,
        load_address,
        item_count,
    ):
        return self.specialty_mart_inventories

    def find_item_archive_members(self, arm9_data, *, item_count, data_member_count):
        return (0, self.item_data_members)

    def parse_item_price(self, data):
        return self.item_prices_by_member[data]

    def shop_schedule_label(self, kind, inventory_id):
        return f"{kind}-{inventory_id}"

    def parse_mart_commands(self, script):
        return self.mart_commands_by_script.get(script[0], ())

    # -- scripts -------------------------------------------------------------
    def parse_pokemon_gift_commands(self, script, *, species_count, item_count):
        return self.gift_commands_by_script.get(script[0], ())

    def parse_egg_gift_commands(self, script, *, species_count):
        return self.egg_commands_by_script.get(script[0], ())

    def parse_static_encounter_commands(self, script, *, species_count):
        return self.static_commands_by_script.get(script[0], ())

    def parse_npc_trade_commands(self, script, *, trade_count):
        return self.trade_commands_by_script.get(script[0], ())

    def parse_npc_trade_record(self, data, *, species_count, item_count):
        return self.npc_trade_records[data[0]]

    def trade_language_name(self, language_id):
        return "English"

    def parse_roaming_activation_commands(self, script):
        return self.roaming_commands_by_script.get(script[0], ())

    def parse_decoration_price_table(self, arm9_data, *, offset, decoration_count):
        return ()


def _header(
    header_id: int,
    *,
    internal_name: str = "ROUTE",
    location_name_id: int = 0,
    matrix_id: int = 0,
    area_data_id: int = 0,
    level_script_id: int = 0,
    text_archive_id: int = 0,
    day_music_id: int = 0,
    night_music_id: int = 0,
    weather_id: int = 0,
    camera_id: int = 0,
    flags: int = 0,
    event_file_id: int = _NULL,
    encounter_id: int = _NULL,
    script_file_id: int = 0,
) -> SimpleNamespace:
    return SimpleNamespace(
        header_id=header_id,
        internal_name=internal_name,
        location_name_id=location_name_id,
        matrix_id=matrix_id,
        area_data_id=area_data_id,
        level_script_id=level_script_id,
        text_archive_id=text_archive_id,
        day_music_id=day_music_id,
        night_music_id=night_music_id,
        weather_id=weather_id,
        camera_id=camera_id,
        flags=flags,
        event_file_id=event_file_id,
        encounter_id=encounter_id,
        script_file_id=script_file_id,
    )


def _profile(*, layout_overrides=None, parameter_overrides=None) -> GameProfile:
    layout = {
        "events": "events.narc",
        "map_matrices": "matrices.narc",
        "map_names": "map_names.bin",
        "messages": "messages.narc",
        "scripts": "scripts.narc",
        "item_data": "item_data.narc",
        "npc_trades": "npc_trades.narc",
    }
    layout.update(layout_overrides or {})
    parameters = {
        "map_header_count": 1,
        "map_header_offset": 0,
        "location_names_member": 0,
        "item_names_member": 1,
        "pokemon_names_member": 2,
        "npc_trade_names_member": 3,
        "common_mart_inventory_offset": 0,
        "specialty_mart_pointer_table_offset": 0,
        "specialty_mart_inventory_count": 0,
    }
    parameters.update(parameter_overrides or {})
    return GameProfile(
        id="test-dppt",
        name="Test DPPt",
        platform="nintendo-ds",
        engine="gen4_platinum",
        base_game="platinum",
        game_codes=("CPUE",),
        rom_versions=(1,),
        hashes=(),
        layout=layout,
        parameters=parameters,
    )


def _result(profile: GameProfile) -> InspectionResult:
    match = HashMatch(
        profile=profile,
        known_hash=KnownHash(algorithm="sha256", value="hash", variant="default"),
    )
    image = SimpleNamespace(hashes=SimpleNamespace(sha256="hash"))
    return InspectionResult(image=image, match=match)


def _patched(engine, archives_by_path):
    platform = SimpleNamespace(
        archive_cls=SimpleNamespace(
            from_bytes=lambda data, **kwargs: archives_by_path[data.decode()]
        ),
        filesystem_from_image=lambda image: SimpleNamespace(
            read=lambda path: path.encode()
        ),
        code_load_address=lambda image: 0x02000000,
    )
    return (
        patch(f"{_MODULE}.get_platform", return_value=platform),
        patch(f"{_MODULE}.get_engine", return_value=SimpleNamespace(locations=engine)),
        patch(f"{_MODULE}.read_code_binary", return_value=bytes(16)),
        patch(f"{_MODULE}.code_load_address", return_value=0x02000000),
    )


_MESSAGE_MEMBERS = (
    b"location-names",
    b"item-names",
    b"pokemon-names",
    b"trade-names",
    b"decoration-names",
)


def _default_archives(profile: GameProfile, *, script_member_count: int = 1) -> dict:
    return {
        profile.layout["messages"]: _Archive(
            len(_MESSAGE_MEMBERS), lambda index: _MESSAGE_MEMBERS[index]
        ),
        profile.layout["events"]: _Archive(1),
        profile.layout["map_matrices"]: _Archive(1),
        profile.layout["scripts"]: _Archive(
            script_member_count, lambda index: bytes((index,))
        ),
        profile.layout["item_data"]: _Archive(0),
        profile.layout["npc_trades"]: _Archive(0),
    }


def _default_engine(headers, *, location_names=("Route 1",)) -> _Engine:
    engine = _Engine(
        headers=headers,
        message_archives={
            b"location-names": location_names,
            b"item-names": ("NONE", "Potion"),
            b"pokemon-names": ("MISSINGNO", "Turtwig"),
            b"trade-names": (),
        },
    )
    engine.events_by_id = {0: SimpleNamespace(warps=(), objects=(), backgrounds=())}
    return engine


class Arm9EventMapDatasetTests(unittest.TestCase):
    def _run(self, result, **kwargs):
        return extract_arm9_event_map_location_dataset(
            result, trainer_dataset={"records": []}, **kwargs
        )

    def test_raises_profile_error_when_metadata_is_missing(self) -> None:
        profile = _profile(layout_overrides={})
        profile = replace(
            profile,
            layout={
                key: value for key, value in profile.layout.items() if key != "scripts"
            },
        )
        result = _result(profile)

        with self.assertRaises(ProfileError):
            self._run(result)

    def test_raises_when_a_header_references_a_missing_event_file(self) -> None:
        headers = (_header(0, event_file_id=5, script_file_id=0),)
        engine = _default_engine(headers)
        profile = _profile()
        archives = _default_archives(profile)
        result = _result(profile)

        get_platform_patch, get_engine_patch, read_code_patch, load_addr_patch = (
            _patched(engine, archives)
        )
        with (
            get_platform_patch,
            get_engine_patch,
            read_code_patch,
            load_addr_patch,
            self.assertRaises(InvalidRomError),
        ):
            self._run(result)

    def test_raises_when_a_header_references_a_missing_script_file(self) -> None:
        headers = (_header(0, event_file_id=_NULL, script_file_id=9),)
        engine = _default_engine(headers)
        profile = _profile()
        archives = _default_archives(profile)
        result = _result(profile)

        get_platform_patch, get_engine_patch, read_code_patch, load_addr_patch = (
            _patched(engine, archives)
        )
        with (
            get_platform_patch,
            get_engine_patch,
            read_code_patch,
            load_addr_patch,
            self.assertRaises(InvalidRomError),
        ):
            self._run(result)

    def test_builds_a_minimal_location_record(self) -> None:
        headers = (
            _header(
                0,
                internal_name="ROUTE_01",
                location_name_id=0,
                event_file_id=_NULL,
                encounter_id=_NULL,
                script_file_id=0,
            ),
        )
        engine = _default_engine(headers)
        profile = _profile()
        archives = _default_archives(profile)
        result = _result(profile)

        get_platform_patch, get_engine_patch, read_code_patch, load_addr_patch = (
            _patched(engine, archives)
        )
        with get_platform_patch, get_engine_patch, read_code_patch, load_addr_patch:
            dataset = self._run(result)

        self.assertEqual(dataset["record_count"], 1)
        self.assertEqual(dataset["schema_version"], 15)
        record = dataset["records"][0]
        self.assertEqual(record["name"], "Route 1")
        self.assertEqual(record["internal_name"], "ROUTE_01")
        self.assertIsNone(record["event_file_id"])
        self.assertIsNone(record["encounter_id"])
        self.assertEqual(record["items"], ())
        self.assertEqual(record["shops"], ())
        self.assertEqual(record["npc_trades"], ())
        self.assertIsNone(record["honey_tree"])
        self.assertIsNone(record["daily_encounter_pool"])
        self.assertEqual(record["game_corner_prizes"], ())

    def test_visible_and_hidden_items_are_classified(self) -> None:
        headers = (_header(0, event_file_id=0, script_file_id=0),)
        engine = _default_engine(headers)
        visible = SimpleNamespace(
            index=0, visible_item_id=1, x=1, z=2, y=0, hidden_flag=None
        )
        hidden = SimpleNamespace(index=1, hidden_item_id=1, x=3, z=4, y=0)
        engine.events_by_id = {
            0: SimpleNamespace(warps=(), objects=(visible,), backgrounds=(hidden,))
        }
        profile = _profile()
        archives = _default_archives(profile)
        result = _result(profile)

        get_platform_patch, get_engine_patch, read_code_patch, load_addr_patch = (
            _patched(engine, archives)
        )
        with get_platform_patch, get_engine_patch, read_code_patch, load_addr_patch:
            dataset = self._run(result)

        self.assertEqual(dataset["visible_item_count"], 1)
        self.assertEqual(dataset["hidden_item_count"], 1)
        items = dataset["records"][0]["items"]
        self.assertEqual([item["kind"] for item in items], ["visible", "hidden"])
        self.assertEqual(items[0]["name"], "Potion")

    def test_dynamic_and_real_warps_are_resolved(self) -> None:
        headers = (
            _header(0, event_file_id=0, script_file_id=0, location_name_id=0),
            _header(1, event_file_id=_NULL, script_file_id=1, location_name_id=1),
        )
        engine = _default_engine(headers, location_names=("Route 1", "Route 2"))
        dynamic_warp = SimpleNamespace(
            index=0, x=1, z=2, destination_header_id=-1, destination_warp_id=-1
        )
        real_warp = SimpleNamespace(
            index=1, x=3, z=4, destination_header_id=1, destination_warp_id=0
        )
        engine.events_by_id = {
            0: SimpleNamespace(
                warps=(dynamic_warp, real_warp), objects=(), backgrounds=()
            )
        }
        profile = _profile()
        archives = _default_archives(profile, script_member_count=2)
        result = _result(profile)

        get_platform_patch, get_engine_patch, read_code_patch, load_addr_patch = (
            _patched(engine, archives)
        )
        with get_platform_patch, get_engine_patch, read_code_patch, load_addr_patch:
            dataset = self._run(result)

        self.assertEqual(dataset["warp_count"], 2)
        self.assertEqual(dataset["dynamic_warp_count"], 1)
        self.assertEqual(dataset["missing_destination_warp_count"], 1)
        warps = dataset["records"][0]["warps"]
        self.assertTrue(warps[0]["dynamic"])
        self.assertIsNone(warps[0]["destination_header_id"])
        self.assertFalse(warps[1]["dynamic"])
        self.assertEqual(warps[1]["destination_header_id"], 1)
        self.assertEqual(warps[1]["destination_name"], "Route 2")
        self.assertFalse(warps[1]["destination_warp_exists"])

    def test_raises_when_a_warp_references_a_missing_header(self) -> None:
        headers = (_header(0, event_file_id=0, script_file_id=0),)
        engine = _default_engine(headers)
        bad_warp = SimpleNamespace(
            index=0, x=1, z=2, destination_header_id=9, destination_warp_id=0
        )
        engine.events_by_id = {
            0: SimpleNamespace(warps=(bad_warp,), objects=(), backgrounds=())
        }
        profile = _profile()
        archives = _default_archives(profile)
        result = _result(profile)

        get_platform_patch, get_engine_patch, read_code_patch, load_addr_patch = (
            _patched(engine, archives)
        )
        with (
            get_platform_patch,
            get_engine_patch,
            read_code_patch,
            load_addr_patch,
            self.assertRaises(InvalidRomError),
        ):
            self._run(result)

    def test_connections_are_derived_from_the_map_matrix(self) -> None:
        headers = (
            _header(0, event_file_id=_NULL, script_file_id=0, location_name_id=0),
            _header(1, event_file_id=_NULL, script_file_id=1, location_name_id=1),
        )
        engine = _default_engine(headers, location_names=("Route 1", "Route 2"))
        engine.matrices_by_id = {
            0: SimpleNamespace(header_ids=(0, 1), width=2, height=1)
        }
        profile = _profile()
        archives = _default_archives(profile, script_member_count=2)
        result = _result(profile)

        get_platform_patch, get_engine_patch, read_code_patch, load_addr_patch = (
            _patched(engine, archives)
        )
        with get_platform_patch, get_engine_patch, read_code_patch, load_addr_patch:
            dataset = self._run(result)

        self.assertEqual(dataset["connection_count"], 2)
        first_connections = dataset["records"][0]["connections"]
        self.assertEqual(first_connections[0]["destination_header_id"], 1)
        self.assertEqual(first_connections[0]["directions"], ("east",))
        second_connections = dataset["records"][1]["connections"]
        self.assertEqual(second_connections[0]["directions"], ("west",))

    def test_roaming_activation_commands_resolve_species(self) -> None:
        headers = (_header(0, event_file_id=_NULL, script_file_id=0),)
        engine = _default_engine(headers)
        engine.roaming_commands_by_script = {0: (SimpleNamespace(slot=0, offset=10),)}
        profile = _profile()
        archives = _default_archives(profile)
        result = _result(profile)

        get_platform_patch, get_engine_patch, read_code_patch, load_addr_patch = (
            _patched(engine, archives)
        )
        with get_platform_patch, get_engine_patch, read_code_patch, load_addr_patch:
            dataset = self._run(result)

        self.assertEqual(dataset["roaming_activation_count"], 1)
        activations = dataset["records"][0]["roaming_activations"]
        self.assertEqual(len(activations), 1)
        self.assertEqual(activations[0]["species_id"], 1)
        self.assertEqual(activations[0]["species_name"], "Turtwig")
        self.assertEqual(activations[0]["command_offset"], 10)

    def test_common_mart_shop_builds_items_and_schedule(self) -> None:
        headers = (_header(0, event_file_id=_NULL, script_file_id=0),)
        engine = _default_engine(headers)
        engine.common_mart_items = (SimpleNamespace(item_id=1, required_badges=None),)
        engine.item_data_members = (0, 1)
        engine.item_prices_by_member = {bytes((0,)): 0, bytes((1,)): 300}
        profile = _profile()
        archives = _default_archives(profile)
        archives[profile.layout["item_data"]] = _Archive(
            2, lambda index: bytes((index,))
        )
        engine.mart_commands_by_script = {
            0: (SimpleNamespace(kind="common", offset=5, inventory_id=0),)
        }
        result = _result(profile)

        get_platform_patch, get_engine_patch, read_code_patch, load_addr_patch = (
            _patched(engine, archives)
        )
        with get_platform_patch, get_engine_patch, read_code_patch, load_addr_patch:
            dataset = self._run(result)

        self.assertEqual(dataset["shop_count"], 1)
        self.assertEqual(dataset["shop_item_reference_count"], 1)
        shop = dataset["records"][0]["shops"][0]
        self.assertEqual(shop["kind"], "common")
        self.assertEqual(shop["currency"], "money")
        self.assertEqual(shop["schedule"], "common-0")
        self.assertEqual(shop["items"][0]["item_id"], 1)
        self.assertEqual(shop["items"][0]["name"], "Potion")
        self.assertEqual(shop["items"][0]["price"], 300)

    def test_shop_item_outside_the_catalog_raises_invalid_rom_error(self) -> None:
        headers = (_header(0, event_file_id=_NULL, script_file_id=0),)
        engine = _default_engine(headers)
        engine.common_mart_items = (SimpleNamespace(item_id=99, required_badges=None),)
        engine.mart_commands_by_script = {
            0: (SimpleNamespace(kind="common", offset=5, inventory_id=0),)
        }
        profile = _profile()
        archives = _default_archives(profile)
        result = _result(profile)

        get_platform_patch, get_engine_patch, read_code_patch, load_addr_patch = (
            _patched(engine, archives)
        )
        with (
            get_platform_patch,
            get_engine_patch,
            read_code_patch,
            load_addr_patch,
            self.assertRaises(InvalidRomError),
        ):
            self._run(result)

    def test_specialty_mart_missing_inventory_raises_invalid_rom_error(self) -> None:
        headers = (_header(0, event_file_id=_NULL, script_file_id=0),)
        engine = _default_engine(headers)
        engine.message_archives[b"decoration-names"] = ()
        engine.mart_commands_by_script = {
            0: (SimpleNamespace(kind="decoration", offset=5, inventory_id=0),)
        }
        profile = _profile(
            parameter_overrides={
                "decoration_names_member": 4,
                "decoration_name_count": 0,
                "decoration_mart_inventory_count": 0,
            }
        )
        archives = _default_archives(profile)
        result = _result(profile)

        get_platform_patch, get_engine_patch, read_code_patch, load_addr_patch = (
            _patched(engine, archives)
        )
        with (
            get_platform_patch,
            get_engine_patch,
            read_code_patch,
            load_addr_patch,
            self.assertRaises(InvalidRomError),
        ):
            self._run(result)

    def test_pokemon_and_egg_gift_commands_are_sorted_by_offset(self) -> None:
        headers = (_header(0, event_file_id=_NULL, script_file_id=0),)
        engine = _default_engine(headers)
        engine.egg_commands_by_script = {0: (SimpleNamespace(species_id=1, offset=20),)}
        engine.gift_commands_by_script = {
            0: (SimpleNamespace(species_id=1, level=5, held_item_id=1, offset=10),)
        }
        profile = _profile()
        archives = _default_archives(profile)
        result = _result(profile)

        get_platform_patch, get_engine_patch, read_code_patch, load_addr_patch = (
            _patched(engine, archives)
        )
        with get_platform_patch, get_engine_patch, read_code_patch, load_addr_patch:
            dataset = self._run(result)

        gifts = dataset["records"][0]["pokemon_gifts"]
        self.assertEqual(dataset["pokemon_gift_count"], 2)
        self.assertEqual([gift["kind"] for gift in gifts], ["pokemon", "egg"])
        self.assertEqual(gifts[0]["held_item_name"], "Potion")
        self.assertEqual(gifts[1]["held_item_id"], None)

    def test_static_encounter_in_non_shared_script_builds_a_record(self) -> None:
        headers = (_header(0, event_file_id=_NULL, script_file_id=0),)
        engine = _default_engine(headers)
        engine.static_commands_by_script = {
            0: (
                SimpleNamespace(species_id=1, level=10, command="WildBattle", offset=7),
            )
        }
        profile = _profile()
        archives = _default_archives(profile)
        result = _result(profile)

        get_platform_patch, get_engine_patch, read_code_patch, load_addr_patch = (
            _patched(engine, archives)
        )
        with get_platform_patch, get_engine_patch, read_code_patch, load_addr_patch:
            dataset = self._run(result)

        self.assertEqual(dataset["static_encounter_count"], 1)
        encounter = dataset["records"][0]["static_encounters"][0]
        self.assertEqual(encounter["species_id"], 1)
        self.assertEqual(encounter["name"], "Turtwig")

    def test_static_encounter_in_shared_script_without_override_raises(self) -> None:
        headers = (
            _header(0, event_file_id=_NULL, script_file_id=0),
            _header(1, event_file_id=_NULL, script_file_id=0, location_name_id=0),
        )
        engine = _default_engine(headers)
        engine.static_commands_by_script = {
            0: (
                SimpleNamespace(species_id=1, level=10, command="WildBattle", offset=7),
            )
        }
        profile = _profile()
        archives = _default_archives(profile)
        result = _result(profile)

        get_platform_patch, get_engine_patch, read_code_patch, load_addr_patch = (
            _patched(engine, archives)
        )
        with (
            get_platform_patch,
            get_engine_patch,
            read_code_patch,
            load_addr_patch,
            self.assertRaises(ProfileError),
        ):
            self._run(result)

    def test_static_encounter_location_metadata_duplicates_raise(self) -> None:
        headers = (_header(0, event_file_id=_NULL, script_file_id=0),)
        engine = _default_engine(headers)
        profile = _profile(
            parameter_overrides={
                "static_encounter_locations": [
                    {"script_member": 0, "command_offset": 7, "map_header_id": 0},
                    {"script_member": 0, "command_offset": 7, "map_header_id": 0},
                ]
            }
        )
        archives = _default_archives(profile)
        result = _result(profile)

        get_platform_patch, get_engine_patch, read_code_patch, load_addr_patch = (
            _patched(engine, archives)
        )
        with (
            get_platform_patch,
            get_engine_patch,
            read_code_patch,
            load_addr_patch,
            self.assertRaises(ProfileError),
        ):
            self._run(result)

    def test_npc_trade_command_resolves_the_trade_record(self) -> None:
        headers = (_header(0, event_file_id=_NULL, script_file_id=0),)
        engine = _default_engine(headers)
        engine.message_archives[b"trade-names"] = ("Nicky", "Owen")
        engine.npc_trade_records = (
            SimpleNamespace(
                requested_species_id=0,
                offered_species_id=1,
                ivs=(31, 31, 31, 31, 31, 31),
                nature="Hardy",
                held_item_id=1,
                ot_id=12345,
                ot_gender=0,
                language_id=2,
                personality=999,
                contest_stats=(0, 0, 0, 0, 0),
                unused_values=(0, 0),
            ),
        )
        engine.trade_commands_by_script = {0: (SimpleNamespace(trade_id=0, offset=3),)}
        profile = _profile()
        archives = _default_archives(profile)
        archives[profile.layout["npc_trades"]] = _Archive(
            1, lambda index: bytes((index,))
        )
        result = _result(profile)

        get_platform_patch, get_engine_patch, read_code_patch, load_addr_patch = (
            _patched(engine, archives)
        )
        with get_platform_patch, get_engine_patch, read_code_patch, load_addr_patch:
            dataset = self._run(result)

        self.assertEqual(dataset["npc_trade_count"], 1)
        trade = dataset["records"][0]["npc_trades"][0]
        self.assertEqual(trade["nickname"], "Nicky")
        self.assertEqual(trade["ot_name"], "Owen")
        self.assertEqual(trade["ot_gender"], "Male")
        self.assertEqual(trade["held_item_name"], "Potion")
        self.assertEqual(trade["requested_species_name"], "MISSINGNO")
        self.assertEqual(trade["offered_species_name"], "Turtwig")

    def test_mismatched_npc_trade_name_count_raises_invalid_rom_error(self) -> None:
        headers = (_header(0, event_file_id=_NULL, script_file_id=0),)
        engine = _default_engine(headers)
        engine.message_archives[b"trade-names"] = ("Only One Name",)
        profile = _profile()
        archives = _default_archives(profile)
        archives[profile.layout["npc_trades"]] = _Archive(1)
        result = _result(profile)

        get_platform_patch, get_engine_patch, read_code_patch, load_addr_patch = (
            _patched(engine, archives)
        )
        with (
            get_platform_patch,
            get_engine_patch,
            read_code_patch,
            load_addr_patch,
            self.assertRaises(InvalidRomError),
        ):
            self._run(result)


if __name__ == "__main__":
    unittest.main()

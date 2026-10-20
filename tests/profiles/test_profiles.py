from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from romwiki.engines.gen5.b2w2.static_encounters import (
    discover_static_encounters as discover_b2w2_static_encounters,
)
from romwiki.engines.registry import get_engine
from romwiki.pipeline.build.sections import enabled_dataset_kinds
from romwiki.platforms.nds.header import NintendoDSHeader
from romwiki.platforms.nds.reader import NintendoDSImage, RomHashes
from romwiki.profiles.loader import ProfileRepository
from romwiki.util.errors import ProfileError
from tests.conftest import make_header


class ProfileRepositoryTests(unittest.TestCase):
    def test_all_data_profiles_explicitly_select_a_type_chart(self) -> None:
        profiles = ProfileRepository.load(Path("profiles")).profiles

        self.assertTrue(profiles)
        self.assertTrue(all(profile.type_chart is not None for profile in profiles))

    def test_loads_clean_platinum_baseline_profile(self) -> None:
        profiles = ProfileRepository.load(Path("profiles")).profiles

        profile = next(value for value in profiles if value.id == "platinum-us")

        self.assertEqual(profile.platform, "nintendo-ds")
        self.assertEqual(profile.engine, "gen4_platinum")
        self.assertEqual(profile.base_game, "platinum")
        self.assertEqual(profile.rom_versions, (0,))
        self.assertNotIn("egg_gifts", profile.parameters)
        self.assertNotIn("pickup_common_item_count", profile.parameters)
        self.assertNotIn("trainer_script_start", profile.parameters)

    def test_loads_hgss_baseline_and_hack_profiles(self) -> None:
        profiles = {
            value.id: value
            for value in ProfileRepository.load(Path("profiles")).profiles
        }

        heartgold = profiles["heartgold-us"]
        soulsilver = profiles["soulsilver-us"]
        sacred_gold = profiles["sacred-gold"]
        storm_silver = profiles["storm-silver"]

        self.assertEqual(heartgold.engine, "gen4_hgss")
        self.assertEqual(heartgold.game_codes, ("IPKE",))
        self.assertEqual(heartgold.sprite_version, "heartgold-soulsilver")
        self.assertEqual(soulsilver.sprite_version, "heartgold-soulsilver")
        self.assertEqual(sacred_gold.sprite_version, "heartgold-soulsilver")
        self.assertEqual(storm_silver.sprite_version, "heartgold-soulsilver")
        self.assertTrue(
            all(
                profile.layout["safari_encounters"] == "a/2/3/0"
                for profile in (heartgold, soulsilver, sacred_gold, storm_silver)
            )
        )
        self.assertEqual(
            heartgold.layout,
            {
                "personal": "a/0/0/2",
                "messages": "a/0/2/7",
                "moves": "a/0/1/1",
                "item_data": "a/0/1/7",
                "learnsets": "a/0/3/3",
                "evolutions": "a/0/3/4",
                "egg_moves": "a/2/2/9",
                "encounters": "a/0/3/7",
                "headbutt_encounters": "a/2/5/2",
                "safari_encounters": "a/2/3/0",
                "events": "a/0/3/2",
                "map_matrices": "a/0/4/1",
                "map_names": "fielddata/maptable/mapname.bin",
                "npc_trades": "a/1/1/2",
                "scripts": "a/0/1/2",
                "trainer_data": "a/0/5/5",
                "trainer_parties": "a/0/5/6",
                "tutor_compatibility": "fielddata/wazaoshie/waza_oshie.bin",
            },
        )
        self.assertEqual(
            heartgold.parameters,
            {
                "ability_names_member": 720,
                "move_names_member": 750,
                "item_names_member": 222,
                "pokemon_names_member": 237,
                "pokemon_descriptions_member": 803,
                "ability_descriptions_member": 722,
                "move_descriptions_member": 749,
                "item_descriptions_member": 221,
                "location_names_member": 279,
                "map_header_offset": 0xF6BE0,
                "map_header_count": 540,
                "null_encounter_id": 255,
                "trainer_names_member": 729,
                "trainer_classes_member": 730,
                "trainer_class_gender_offset": 0xFFB90,
                "starter_species_overlay_id": 61,
                "starter_species_offset": 0x1A98,
                "starter_species_count": 3,
                "trainer_variant_contract": "hgss-retail-v1",
                "npc_trade_names_member": 200,
                "npc_trades_unused": [6, 7],
                "pickup_overlay_id": 12,
                "shop_catalog_locator": "298E0402618E0402998E0402B98E0402",
                "tutor_overlay_id": 1,
                "tutor_move_offset": 0x23AE0,
            },
        )
        self.assertEqual(
            enabled_dataset_kinds(heartgold),
            (
                "pokemon",
                "abilities",
                "moves",
                "items",
                "encounters",
                "trainers",
                "locations",
            ),
        )
        self.assertEqual(soulsilver.game_codes, ("IPGE",))
        self.assertEqual(soulsilver.base_game, "soulsilver")
        self.assertEqual(soulsilver.parameters["pokemon_descriptions_member"], 804)
        self.assertEqual(sacred_gold.hashes[0].variant, "complete-v1.05")
        self.assertEqual(storm_silver.hashes[0].variant, "complete-v1.05")
        self.assertEqual(sacred_gold.layout, heartgold.layout)
        self.assertEqual(storm_silver.layout, soulsilver.layout)
        self.assertTrue(sacred_gold.parameters["learnsets_allow_truncated"])
        self.assertTrue(storm_silver.parameters["encounters_allow_truncated"])
        self.assertTrue(
            sacred_gold.parameters["events_allow_incorrect_data_block_size"]
        )

        engine = get_engine(heartgold.engine)
        self.assertEqual(
            engine.dataset_kinds,
            frozenset(
                {
                    "pokemon",
                    "abilities",
                    "moves",
                    "items",
                    "encounters",
                    "trainers",
                    "locations",
                }
            ),
        )
        self.assertEqual(engine.required_dataset_kinds, frozenset({"pokemon"}))
        self.assertEqual(engine.formats.encounters, "conditional")
        self.assertEqual(engine.formats.locations, "encounter-map")
        self.assertEqual(engine.formats.trainers, "class-gender")
        self.assertEqual(engine.formats.pickup, "locator-tables")
        self.assertEqual(engine.formats.tutors, "overlay-archive")
        self.assertIn("detached-npc-trades", engine.capabilities)

    def test_identifies_exact_hgss_hashes_and_rejects_near_matches(self) -> None:
        repository = ProfileRepository.load(Path("profiles"))
        cases = (
            (
                "IPKE",
                "65f02a56842b75aa92d775d56d657a56fe3fa993550b04dc20704ab82d760105",
                "heartgold-us",
            ),
            (
                "IPGE",
                "51d0f94a16af7d77c067b4cb7d821ba890a13203a2e2c76049623332c0582e20",
                "soulsilver-us",
            ),
        )
        for game_code, sha256, profile_id in cases:
            with self.subTest(profile=profile_id):
                header_data = bytearray(make_header())
                header_data[0x0C:0x10] = game_code.encode("ascii")
                header_data[0x1E] = 0
                image = NintendoDSImage(
                    path=Path("test.nds"),
                    size=0x8000,
                    header=NintendoDSHeader.from_bytes(bytes(header_data)),
                    hashes=RomHashes(md5="", sha1="", sha256=sha256),
                )

                match = repository.identify(image)
                self.assertIsNotNone(match)
                assert match is not None
                self.assertEqual(match.profile.id, profile_id)

                near_match = NintendoDSImage(
                    path=image.path,
                    size=image.size,
                    header=image.header,
                    hashes=RomHashes(
                        md5="",
                        sha1="",
                        sha256=f"{sha256[:-1]}{'1' if sha256[-1] != '1' else '0'}",
                    ),
                )
                self.assertIsNone(repository.identify(near_match))

    def test_hgss_profile_contract_rejects_unverified_layout(self) -> None:
        profiles = {
            value.id: value
            for value in ProfileRepository.load(Path("profiles")).profiles
        }
        heartgold = replace(
            profiles["heartgold-us"],
            layout={**profiles["heartgold-us"].layout, "unknown": "a/0/3/7"},
        )

        with self.assertRaisesRegex(ProfileError, "unsupported layout: unknown"):
            enabled_dataset_kinds(heartgold)

    def test_loads_black_and_white_baseline_profiles(self) -> None:
        profiles = {
            value.id: value
            for value in ProfileRepository.load(Path("profiles")).profiles
        }

        black = profiles["black-us"]
        white = profiles["white-us"]

        self.assertEqual(black.platform, "nintendo-ds")
        self.assertEqual(black.engine, "gen5_bw")
        self.assertEqual(black.base_game, "black")
        self.assertEqual(black.game_codes, ("IRBO",))
        self.assertEqual(black.rom_versions, (0,))
        self.assertEqual(black.layout["personal"], "a/0/1/6")
        self.assertEqual(black.layout["messages"], "a/0/0/2")
        self.assertEqual(black.layout["item_data"], "a/0/2/4")
        self.assertEqual(black.layout["moves"], "a/0/2/1")
        self.assertEqual(black.layout["learnsets"], "a/0/1/8")
        self.assertEqual(black.layout["evolutions"], "a/0/1/9")
        self.assertEqual(black.layout["egg_moves"], "a/1/2/3")
        self.assertEqual(black.layout["encounters"], "a/1/2/6")
        self.assertEqual(black.layout["trainer_data"], "a/0/9/2")
        self.assertEqual(black.layout["trainer_parties"], "a/0/9/3")
        self.assertEqual(black.layout["map_headers"], "a/0/1/2")
        self.assertEqual(black.layout["npc_trades"], "a/1/6/5")
        self.assertEqual(black.layout["scripts"], "a/0/5/7")
        self.assertEqual(black.parameters["pokemon_names_member"], 70)
        self.assertEqual(black.parameters["ability_names_member"], 182)
        self.assertEqual(black.parameters["move_names_member"], 203)
        self.assertEqual(black.parameters["item_names_member"], 54)
        self.assertNotIn("machine_move_prefix", black.parameters)
        self.assertNotIn("pickup_table_locator", black.parameters)
        self.assertEqual(black.parameters["trainer_names_member"], 190)
        self.assertEqual(black.parameters["trainer_classes_member"], 191)
        self.assertEqual(black.parameters["map_names_member"], 89)
        self.assertEqual(black.parameters["npc_trade_names_member"], 35)
        self.assertEqual(
            black.parameters["npc_trades_unused"], [1, 3, 7, 8, 9, 10, 11, 12]
        )
        self.assertNotIn("static_pokemon", black.parameters)
        self.assertNotIn("static_pokemon_egg_indices", black.parameters)
        self.assertEqual(black.sprite_version, "black-white")

        self.assertEqual(white.engine, "gen5_bw")
        self.assertEqual(white.base_game, "white")
        self.assertEqual(white.game_codes, ("IRAO",))
        self.assertEqual(white.layout["messages"], "a/0/0/2")
        self.assertEqual(white.parameters["pokemon_names_member"], 70)
        self.assertEqual(white.layout["personal"], "a/0/1/6")
        self.assertEqual(white.layout["item_data"], "a/0/2/4")
        self.assertEqual(white.layout["trainer_data"], "a/0/9/2")
        self.assertEqual(white.layout["map_headers"], "a/0/1/2")
        self.assertEqual(white.layout["npc_trades"], "a/1/6/5")
        self.assertEqual(white.layout["scripts"], "a/0/5/7")
        self.assertEqual(
            white.parameters["npc_trades_unused"], [0, 2, 7, 8, 9, 10, 11, 12]
        )
        self.assertNotIn("static_pokemon", white.parameters)

    def test_loads_blaze_black_and_volt_white_profiles(self) -> None:
        profiles = {
            value.id: value
            for value in ProfileRepository.load(Path("profiles")).profiles
        }

        blaze = profiles["blaze-black"]
        volt = profiles["volt-white"]

        self.assertEqual(blaze.engine, "gen5_bw")
        self.assertEqual(blaze.base_game, "black")
        self.assertEqual(blaze.game_codes, ("IRBO",))
        self.assertEqual(blaze.hashes[0].variant, "full-v3.1")
        self.assertEqual(
            blaze.hashes[0].value,
            "340c1416b2b107a59c9305c43747761804edce8e876c364abee1f0189bd768ac",
        )
        self.assertEqual(volt.engine, "gen5_bw")
        self.assertEqual(volt.base_game, "white")
        self.assertEqual(volt.game_codes, ("IRAO",))
        self.assertEqual(volt.hashes[0].variant, "full-v3.1")
        self.assertEqual(
            volt.hashes[0].value,
            "232043c9e3f979fff9e1fd67b78d759928e7849b4c2516477b43538fbf7bf851",
        )

    def test_loads_black_2_and_white_2_baseline_profiles(self) -> None:
        profiles = {
            value.id: value
            for value in ProfileRepository.load(Path("profiles")).profiles
        }

        black_2 = profiles["black-2-us"]
        white_2 = profiles["white-2-us"]

        self.assertEqual(black_2.engine, "gen5_b2w2")
        self.assertEqual(black_2.game_codes, ("IREO",))
        self.assertEqual(black_2.layout["trainer_data"], "a/0/9/1")
        self.assertEqual(black_2.layout["encounters"], "a/1/2/7")
        self.assertEqual(black_2.parameters["pokemon_names_member"], 90)
        self.assertEqual(black_2.parameters["move_names_member"], 403)
        self.assertEqual(black_2.layout["hidden_grottos"], "a/2/7/3")
        self.assertEqual(black_2.parameters["hidden_grotto_version_group"], 1)
        self.assertEqual(black_2.parameters["hidden_grotto_dispatch_base"], 10795)
        self.assertEqual(black_2.parameters["hidden_grotto_record_count"], 20)
        self.assertEqual(black_2.parameters["swarm_table_offset"], 0x50BFC)
        self.assertNotIn("static_pokemon", black_2.parameters)
        self.assertNotIn("static_pokemon_egg_indices", black_2.parameters)
        self.assertEqual(
            get_engine(black_2.engine).formats.static_encounters, "script-commands"
        )
        self.assertIs(
            get_engine(black_2.engine).static_encounters.discover_static_encounters,
            discover_b2w2_static_encounters,
        )
        self.assertEqual(black_2.sprite_version, "black-white")
        self.assertEqual(white_2.engine, "gen5_b2w2")
        self.assertEqual(white_2.game_codes, ("IRDO",))
        self.assertEqual(white_2.hashes[0].algorithm, "sha256")
        self.assertEqual(white_2.parameters["hidden_grotto_version_group"], 0)
        self.assertEqual(white_2.parameters["swarm_table_offset"], 0x50BF0)
        self.assertNotIn("static_pokemon", white_2.parameters)
        self.assertNotIn("static_pokemon_egg_indices", white_2.parameters)
        self.assertEqual(white_2.sprite_version, "black-white")

    def test_loads_blaze_black_2_and_volt_white_2_profiles(self) -> None:
        profiles = {
            value.id: value
            for value in ProfileRepository.load(Path("profiles")).profiles
        }

        blaze = profiles["blaze-black-2"]
        volt = profiles["volt-white-2"]

        self.assertEqual(blaze.engine, "gen5_b2w2")
        self.assertEqual(blaze.base_game, "black-2")
        self.assertEqual(blaze.hashes[0].variant, "complete-v1.1")
        self.assertEqual(blaze.sprite_version, "black-white")
        self.assertNotIn("static_pokemon", blaze.parameters)
        self.assertNotIn("static_pokemon_egg_indices", blaze.parameters)
        self.assertEqual(volt.engine, "gen5_b2w2")
        self.assertEqual(volt.base_game, "white-2")
        self.assertEqual(volt.hashes[0].variant, "complete-v1.1")
        self.assertEqual(volt.sprite_version, "black-white")
        self.assertNotIn("static_pokemon", volt.parameters)
        self.assertNotIn("static_pokemon_egg_indices", volt.parameters)

    def test_loads_blaze_black_2_and_volt_white_2_redux_profiles(self) -> None:
        profiles = {
            value.id: value
            for value in ProfileRepository.load(Path("profiles")).profiles
        }

        blaze = profiles["blaze-black-2-redux"]
        volt = profiles["volt-white-2-redux"]

        self.assertEqual(blaze.engine, "gen5_b2w2")
        self.assertEqual(blaze.base_game, "black-2")
        self.assertEqual(blaze.hashes[0].variant, "complete-v1.4.1")
        self.assertEqual(
            blaze.hashes[0].value,
            "332d07576e2077b4ef91e394603d144108098b7624c6a918b175f90530c0036a",
        )
        self.assertEqual(blaze.game_codes, ("IREO",))
        self.assertEqual(blaze.type_chart.chart, "gen5")
        self.assertEqual(blaze.type_chart.additional_types, ("fairy",))
        self.assertEqual(blaze.type_chart.overrides["dragon>fairy"], "0")
        self.assertEqual(blaze.type_chart.overrides["ghost>steel"], "1")
        self.assertEqual(blaze.type_names[17], "fairy")
        self.assertTrue(blaze.parameters["field_archives_allow_trailing_data"])
        self.assertTrue(blaze.parameters["map_headers_allow_trailing_data"])
        self.assertTrue(blaze.parameters["map_headers_allow_incorrect_data_block_size"])
        self.assertTrue(blaze.parameters["repair_invalid_secondary_egg_group"])
        self.assertEqual(blaze.parameters["overworld_objects_unused"], [464])
        self.assertEqual(blaze.parameters["pickup_table_locator"], "19005C003500")
        self.assertEqual(volt.engine, "gen5_b2w2")
        self.assertEqual(volt.base_game, "white-2")
        self.assertEqual(volt.hashes[0].variant, "complete-v1.4.1")
        self.assertEqual(
            volt.hashes[0].value,
            "cf75c45ef07596e31f9d5bf4babde67b60a028e6b85eb811c14a7d4715a21120",
        )
        self.assertEqual(volt.game_codes, ("IRDO",))
        self.assertEqual(volt.type_chart.chart, "gen5")
        self.assertEqual(volt.type_chart.additional_types, ("fairy",))
        self.assertEqual(volt.type_chart.overrides["dragon>fairy"], "0")
        self.assertEqual(volt.type_chart.overrides["dark>steel"], "1")
        self.assertEqual(volt.type_names[17], "fairy")
        self.assertTrue(volt.parameters["field_archives_allow_trailing_data"])
        self.assertTrue(volt.parameters["map_headers_allow_trailing_data"])
        self.assertTrue(volt.parameters["map_headers_allow_incorrect_data_block_size"])
        self.assertTrue(volt.parameters["repair_invalid_secondary_egg_group"])
        self.assertEqual(volt.parameters["overworld_objects_unused"], [464])
        self.assertEqual(volt.parameters["pickup_table_locator"], "19005C003500")

    def test_matches_a_known_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            profile_path = Path(directory) / "test.toml"
            profile_path.write_text(
                """
[profile]
id = "test"
name = "Test Profile"
platform = "nintendo-ds"
engine = "gen4_platinum"
base_game = "platinum"
[header]
game_codes = ["CPUE"]
rom_versions = [1]
[semantics.types]
9 = "fairy"
[semantics.moves]
66 = "play-rough"
[[hashes]]
algorithm = "sha256"
value = "abcd"
variant = "test"
""".strip(),
                encoding="utf-8",
            )
            image = NintendoDSImage(
                path=Path("test.nds"),
                size=0x8000,
                header=NintendoDSHeader.from_bytes(make_header()),
                hashes=RomHashes(md5="", sha1="", sha256="abcd"),
            )

            match = ProfileRepository.load(Path(directory)).identify(image)

        self.assertIsNotNone(match)
        assert match is not None
        self.assertEqual(match.profile.id, "test")
        self.assertEqual(match.profile.type_names, {9: "fairy"})
        self.assertEqual(match.profile.move_names, {66: "play-rough"})
        self.assertEqual(match.known_hash.variant, "test")

    def test_profile_inherits_and_overrides_nested_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "base.toml").write_text(
                """
[profile]
id = "base"
name = "Base"
platform = "nintendo-ds"
engine = "gen4_platinum"
base_game = "platinum"
[header]
game_codes = ["CPUE"]
rom_versions = [0]
[layout]
personal = "base/personal"
messages = "base/messages"
[parameters]
member = 1
[[hashes]]
algorithm = "sha256"
value = "base"
variant = "base"
""".strip(),
                encoding="utf-8",
            )
            (root / "child.toml").write_text(
                """
[profile]
id = "child"
name = "Child"
extends = "base"
[layout]
messages = "child/messages"
[parameters]
member = 2
[[hashes]]
algorithm = "sha256"
value = "child"
variant = "child"
""".strip(),
                encoding="utf-8",
            )

            profiles = {
                profile.id: profile for profile in ProfileRepository.load(root).profiles
            }

        child = profiles["child"]
        self.assertEqual(child.parent, "base")
        self.assertIsNone(profiles["base"].parent)
        self.assertEqual(child.platform, "nintendo-ds")
        self.assertEqual(child.layout["personal"], "base/personal")
        self.assertEqual(child.layout["messages"], "child/messages")
        self.assertEqual(child.parameters["member"], 2)
        self.assertEqual([value.value for value in child.hashes], ["child"])

    def test_resolves_symbols_and_specials_from_the_symbol_table(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "symbols").mkdir()
            for table, offset, special in (("base", 0x100, 7), ("child", 0x200, 9)):
                (root / "symbols" / f"{table}.toml").write_text(
                    f"""
[symbols.gTable]
offset = {offset:#x}
size = 40
[symbols.gOther]
offset = 0x300
size = 4
[specials]
SomeHandler = {special}
""".strip(),
                    encoding="utf-8",
                )
            (root / "base.toml").write_text(
                """
[profile]
id = "base"
symbols = "base"
name = "Base"
platform = "gba"
engine = "gen3_frlg"
base_game = "firered"
[header]
game_codes = ["BPRE"]
rom_versions = [0]
[parameters]
table_symbol = "gTable"
other_symbol = "gOther"
handler_special = "SomeHandler"
[[hashes]]
algorithm = "sha256"
value = "base"
variant = "base"
""".strip(),
                encoding="utf-8",
            )
            (root / "child.toml").write_text(
                """
[profile]
id = "child"
symbols = "child"
name = "Child"
extends = "base"
[parameters]
other_offset = 0x400
[[hashes]]
algorithm = "sha256"
value = "child"
variant = "child"
""".strip(),
                encoding="utf-8",
            )

            profiles = {
                profile.id: profile for profile in ProfileRepository.load(root).profiles
            }

        base, child = profiles["base"], profiles["child"]
        self.assertEqual(base.int_parameter("table_offset"), 0x100)
        self.assertEqual(base.int_parameter("handler_special"), 7)
        self.assertNotIn("table_symbol", base.parameters)
        self.assertEqual(base.symbols["table_offset"].name, "gTable")
        # An inherited symbol resolves against the child's own table, and an
        # explicit offset wins over it.
        self.assertEqual(child.int_parameter("table_offset"), 0x200)
        self.assertEqual(child.int_parameter("handler_special"), 9)
        self.assertEqual(child.int_parameter("other_offset"), 0x400)
        self.assertNotIn("other_offset", child.symbols)

    def test_rejects_an_unknown_symbol(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "symbols").mkdir()
            (root / "symbols" / "base.toml").write_text(
                "[symbols.gTable]\noffset = 0x100\nsize = 40\n", encoding="utf-8"
            )
            (root / "base.toml").write_text(
                """
[profile]
id = "base"
symbols = "base"
name = "Base"
platform = "gba"
engine = "gen3_frlg"
base_game = "firered"
[header]
game_codes = ["BPRE"]
rom_versions = [0]
[parameters]
table_symbol = "gMissing"
[[hashes]]
algorithm = "sha256"
value = "base"
variant = "base"
""".strip(),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ProfileError, "gMissing"):
                ProfileRepository.load(root)

    def test_rejects_unknown_profile_parent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "child.toml"
            path.write_text(
                """
[profile]
id = "child"
name = "Child"
extends = "missing"
[[hashes]]
algorithm = "sha256"
value = "child"
variant = "child"
""".strip(),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ProfileError, "unknown profile missing"):
                ProfileRepository.load(Path(directory))

    def test_loads_explicit_location_section_names(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "game.toml"
            path.write_text(
                """
[profile]
id = "example"
name = "Example"
platform = "nintendo-ds"
engine = "gen4_hgss"
base_game = "heartgold"
[header]
game_codes = ["TEST"]
rom_versions = [0]
[location_sections.by_header]
"12" = "Example Cave B1F"
[location_sections.by_internal_name]
MAP_CUSTOM = "Example Cave 2F"
[[hashes]]
algorithm = "sha256"
value = "00"
variant = "test"
""".strip(),
                encoding="utf-8",
            )

            profile = ProfileRepository.load(Path(directory)).profiles[0]

        self.assertEqual(profile.location_sections.by_header, {12: "Example Cave B1F"})
        self.assertEqual(
            profile.location_sections.by_internal_name,
            {"MAP_CUSTOM": "Example Cave 2F"},
        )

    def test_inherited_profile_cannot_silently_inherit_a_type_chart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "base.toml").write_text(
                """
[profile]
id = "base"
name = "Base"
platform = "nintendo-ds"
engine = "gen4_platinum"
base_game = "platinum"
[header]
game_codes = ["CPUE"]
rom_versions = [0]
[type_chart]
chart = "gen4"
[[hashes]]
algorithm = "sha256"
value = "base"
variant = "base"
""".strip(),
                encoding="utf-8",
            )
            (root / "child.toml").write_text(
                """
[profile]
id = "child"
name = "Child"
extends = "base"
[[hashes]]
algorithm = "sha256"
value = "child"
variant = "child"
""".strip(),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ProfileError, "explicitly declare"):
                ProfileRepository.load(root)

    def test_inherited_profile_declares_its_own_trainer_variant_contract(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "base.toml").write_text(
                """
[profile]
id = "base"
name = "Base"
platform = "nintendo-ds"
engine = "gen4_platinum"
base_game = "platinum"
[header]
game_codes = ["CPUE"]
rom_versions = [0]
[type_chart]
chart = "gen4"
[parameters]
trainer_variant_contract = "platinum-retail-v1"
[[hashes]]
algorithm = "sha256"
value = "base"
variant = "base"
""".strip(),
                encoding="utf-8",
            )
            for profile_id, parameters in (
                ("unverified", ""),
                (
                    "verified",
                    '[parameters]\ntrainer_variant_contract = "verified-v1"\n',
                ),
            ):
                (root / f"{profile_id}.toml").write_text(
                    f"""
[profile]
id = "{profile_id}"
name = "Child"
extends = "base"
[type_chart]
chart = "gen4"
{parameters}[[hashes]]
algorithm = "sha256"
value = "{profile_id}"
variant = "{profile_id}"
""".strip(),
                    encoding="utf-8",
                )

            profiles = {
                profile.id: profile for profile in ProfileRepository.load(root).profiles
            }

        self.assertEqual(
            profiles["base"].parameters["trainer_variant_contract"],
            "platinum-retail-v1",
        )
        self.assertNotIn("trainer_variant_contract", profiles["unverified"].parameters)
        self.assertEqual(
            profiles["verified"].parameters["trainer_variant_contract"], "verified-v1"
        )

    def test_inherited_profile_requires_its_own_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "base.toml").write_text(
                """
[profile]
id = "base"
name = "Base"
platform = "nintendo-ds"
engine = "gen4_platinum"
base_game = "platinum"
[header]
game_codes = ["CPUE"]
rom_versions = [0]
[[hashes]]
algorithm = "sha256"
value = "base"
variant = "base"
""".strip(),
                encoding="utf-8",
            )
            (root / "child.toml").write_text(
                """
[profile]
id = "child"
name = "Child"
extends = "base"
""".strip(),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ProfileError, "must define its own hashes"):
                ProfileRepository.load(root)

    def test_rejects_profile_inheritance_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for profile_id, parent_id in (("first", "second"), ("second", "first")):
                (root / f"{profile_id}.toml").write_text(
                    f"""
[profile]
id = "{profile_id}"
name = "{profile_id}"
extends = "{parent_id}"
[[hashes]]
algorithm = "sha256"
value = "{profile_id}"
variant = "{profile_id}"
""".strip(),
                    encoding="utf-8",
                )

            with self.assertRaisesRegex(ProfileError, "inheritance cycle"):
                ProfileRepository.load(root)

    def test_rejects_invalid_sprite_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            profile_path = Path(directory) / "test.toml"
            profile_path.write_text(
                """
[profile]
id = "test"
name = "Test Profile"
platform = "nintendo-ds"
engine = "gen4_platinum"
base_game = "platinum"
[header]
game_codes = ["CPUE"]
rom_versions = [1]
[reference]
sprite_version = "Platinum Version"
[[hashes]]
algorithm = "sha256"
value = "abcd"
variant = "test"
""".strip(),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ProfileError, "Invalid sprite version"):
                ProfileRepository.load(Path(directory))

    def test_rejects_invalid_type_semantic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            profile_path = Path(directory) / "test.toml"
            profile_path.write_text(
                """
[profile]
id = "test"
name = "Test Profile"
platform = "nintendo-ds"
engine = "gen4_platinum"
base_game = "platinum"
[header]
game_codes = ["CPUE"]
rom_versions = [1]
[semantics.types]
9 = "Fairy Type"
[[hashes]]
algorithm = "sha256"
value = "abcd"
variant = "test"
""".strip(),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ProfileError, "Invalid type semantic"):
                ProfileRepository.load(Path(directory))

    def test_rejects_profile_missing_platform(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            profile_path = Path(directory) / "test.toml"
            profile_path.write_text(
                """
[profile]
id = "test"
name = "Test Profile"
engine = "gen4_platinum"
base_game = "platinum"
[header]
game_codes = ["CPUE"]
rom_versions = [1]
[[hashes]]
algorithm = "sha256"
value = "abcd"
variant = "test"
""".strip(),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ProfileError, "Invalid profile"):
                ProfileRepository.load(Path(directory))


if __name__ == "__main__":
    unittest.main()

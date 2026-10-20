from __future__ import annotations

import gzip
import json
import tempfile
import unittest
from pathlib import Path

from romwiki.sources import PokeDBGeneration
from romwiki.sources.pokedb import pack_pokedb
from romwiki.util.errors import DataSourceError


class PokeDBSpriteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pokedb = PokeDBGeneration(
            pokemon_by_id={},
            pokemon_by_name={},
            pokemon_by_species={},
            abilities_by_id={},
            items_by_id={},
        )

    def test_selects_exact_version_sprite(self) -> None:
        reference = {
            "sprites": {
                "front_default": "https://example.test/default.png",
                "versions": {
                    "platinum": {"front_default": "https://example.test/platinum.png"}
                },
            }
        }

        sprite = self.pokedb.pokemon_sprite(reference, "platinum")

        assert sprite is not None
        self.assertEqual(sprite["url"], "https://example.test/platinum.png")
        self.assertEqual(sprite["source"], "PokéAPI sprites")

    def test_returns_all_available_version_sprites_in_display_order(self) -> None:
        reference = {
            "sprites": {
                "versions": {
                    "platinum": {
                        "back_shiny": "https://example.test/back-shiny.png",
                        "front_default": "https://example.test/front.png",
                        "back_default": "https://example.test/back.png",
                        "front_shiny": "https://example.test/front-shiny.png",
                    }
                }
            }
        }

        sprites = self.pokedb.pokemon_sprites(reference, "platinum")

        self.assertEqual(
            [sprite["key"] for sprite in sprites],
            ["front_default", "front_shiny", "back_default", "back_shiny"],
        )

    def test_includes_animated_variants_when_present(self) -> None:
        reference = {
            "sprites": {
                "versions": {
                    "black-white": {
                        "front_default": "https://example.test/front.png",
                        "front_shiny": "https://example.test/front-shiny.png",
                        "animated": {
                            "front_default": "https://example.test/front.gif",
                            "front_shiny": "https://example.test/front-shiny.gif",
                            "back_default": None,
                        },
                    }
                }
            }
        }

        sprites = self.pokedb.pokemon_sprites(reference, "black-white")

        self.assertEqual(
            [sprite["key"] for sprite in sprites],
            [
                "front_default",
                "front_shiny",
                "front_default_animated",
                "front_shiny_animated",
            ],
        )
        animated = {sprite["key"]: sprite["url"] for sprite in sprites}
        self.assertEqual(
            animated["front_default_animated"], "https://example.test/front.gif"
        )

    def test_falls_back_and_rejects_non_https_urls(self) -> None:
        fallback = self.pokedb.pokemon_sprite(
            {"sprites": {"front_default": "https://example.test/default.png"}},
            "missing-version",
        )
        rejected = self.pokedb.pokemon_sprite(
            {"sprites": {"front_default": "http://example.test/default.png"}},
            None,
        )

        assert fallback is not None
        self.assertEqual(fallback["url"], "https://example.test/default.png")
        self.assertIsNone(rejected)

    def test_portrait_prefers_official_artwork_over_home(self) -> None:
        reference = {
            "sprites": {
                "front_default": "https://example.test/default.png",
                "other": {
                    "official-artwork": {
                        "front_default": "https://example.test/artwork.png"
                    },
                    "home": {"front_default": "https://example.test/home.png"},
                },
            }
        }

        portrait = self.pokedb.pokemon_portrait(reference)

        assert portrait is not None
        self.assertEqual(portrait["url"], "https://example.test/artwork.png")
        self.assertEqual(portrait["key"], "official-artwork")

    def test_portrait_falls_back_to_home_then_none(self) -> None:
        with_home = self.pokedb.pokemon_portrait(
            {
                "sprites": {
                    "other": {
                        "home": {"front_default": "https://example.test/home.png"}
                    }
                }
            }
        )
        without_artwork = self.pokedb.pokemon_portrait(
            {"sprites": {"front_default": "https://example.test/default.png"}}
        )
        rejects_non_https = self.pokedb.pokemon_portrait(
            {
                "sprites": {
                    "other": {"home": {"front_default": "http://example.test/home.png"}}
                }
            }
        )

        assert with_home is not None
        self.assertEqual(with_home["url"], "https://example.test/home.png")
        self.assertIsNone(without_artwork)
        self.assertIsNone(rejects_non_https)

    def test_cry_prefers_latest_over_legacy(self) -> None:
        reference = {
            "cries": {
                "legacy": "https://example.test/legacy.ogg",
                "latest": "https://example.test/latest.ogg",
            }
        }

        cry = self.pokedb.pokemon_cry(reference)

        assert cry is not None
        self.assertEqual(cry["url"], "https://example.test/latest.ogg")
        self.assertEqual(cry["key"], "latest")
        self.assertEqual(cry["source"], "PokéAPI cries")

    def test_cry_falls_back_to_legacy_then_none(self) -> None:
        legacy_only = self.pokedb.pokemon_cry(
            {"cries": {"legacy": "https://example.test/legacy.ogg"}}
        )
        missing = self.pokedb.pokemon_cry({"cries": {}})
        rejects_non_https = self.pokedb.pokemon_cry(
            {"cries": {"legacy": "http://example.test/legacy.ogg"}}
        )

        assert legacy_only is not None
        self.assertEqual(legacy_only["url"], "https://example.test/legacy.ogg")
        self.assertIsNone(missing)
        self.assertIsNone(rejects_non_https)

    def test_matches_rom_item_names_without_using_rom_item_ids(self) -> None:
        pokedb = PokeDBGeneration(
            pokemon_by_id={},
            pokemon_by_name={},
            pokemon_by_species={},
            abilities_by_id={},
            items_by_id={213: "bright-powder"},
        )

        self.assertEqual(pokedb.item_slug("BrightPowder"), "bright-powder")
        self.assertEqual(pokedb.item_slug("Odd Invitation"), "odd-invitation")

    def test_matches_abbreviated_rom_item_names(self) -> None:
        reference_names = (
            "paralyze-heal",
            "x-defense",
            "x-defense-2",
            "x-defense-3",
            "x-defense-6",
            "x-sp-atk",
            "x-sp-atk-2",
            "x-sp-atk-3",
            "x-sp-atk-6",
            "dowsing-machine",
            "colress-machine",
            "black-apricorn",
            "blue-apricorn",
            "green-apricorn",
            "pink-apricorn",
            "white-apricorn",
            "yellow-apricorn",
        )
        pokedb = PokeDBGeneration(
            pokemon_by_id={},
            pokemon_by_name={},
            pokemon_by_species={},
            abilities_by_id={},
            items_by_id=dict(enumerate(reference_names, start=1)),
        )
        expected = {
            "Parlyz Heal": "paralyze-heal",
            "X Defend": "x-defense",
            "X Defend 2": "x-defense-2",
            "X Defend 6": "x-defense-6",
            "X Special": "x-sp-atk",
            "X Special 3": "x-sp-atk-3",
            "X Special 6": "x-sp-atk-6",
            "Dowsing MCHN": "dowsing-machine",
            "Colress MCHN": "colress-machine",
            "Blk Apricorn": "black-apricorn",
            "Blu Apricorn": "blue-apricorn",
            "Ylw Apricorn": "yellow-apricorn",
        }

        for rom_name, reference_slug in expected.items():
            with self.subTest(rom_name=rom_name):
                self.assertEqual(pokedb.item_reference_slug(rom_name), reference_slug)

        self.assertEqual(pokedb.item_slug("Parlyz Heal"), "parlyz-heal")

    def test_only_uses_item_name_normalizations_that_exist_in_pokedb(self) -> None:
        pokedb = PokeDBGeneration(
            pokemon_by_id={},
            pokemon_by_name={},
            pokemon_by_species={},
            abilities_by_id={},
            items_by_id={},
        )

        self.assertEqual(pokedb.item_reference_slug("Imaginary MCHN"), "imaginary-mchn")
        self.assertEqual(pokedb.item_reference_slug("X Special 9"), "x-special-9")
        self.assertEqual(pokedb.item_reference_slug("Blu Apricorn"), "blu-apricorn")

    def test_selects_descriptive_and_base_game_reference_data(self) -> None:
        reference = {
            "source_url": "https://pokeapi.co/api/v2/pokemon/1/",
            "genus": "Seed Pokémon",
            "height": 7,
            "weight": 69,
            "types": ["grass", "poison"],
            "abilities": [{"name": "overgrow", "slot": 1}],
            "stats": {
                "hp": 45,
                "attack": 49,
                "defense": 49,
                "speed": 45,
                "special-attack": 65,
                "special-defense": 65,
            },
            "flavor_text": {
                "diamond": "Diamond entry.",
                "platinum": "Platinum entry.",
            },
        }

        result = self.pokedb.pokemon_reference(reference, "platinum")

        self.assertEqual(result["flavor_text"], "Platinum entry.")
        self.assertEqual(result["flavor_text_version"], "platinum")
        self.assertEqual(result["genus"], "Seed Pokémon")
        # Battle facts stay ROM-sourced and are not duplicated in the snapshot.
        self.assertNotIn("base_stats", result)
        self.assertNotIn("types", result)
        self.assertNotIn("abilities", result)

    def test_versioned_text_falls_back_to_the_earliest_version(self) -> None:
        reference = {
            "flavor_text": {
                "zz-unknown": "Unknown entry.",
                "heartgold": "HeartGold entry.",
                "aa-unknown": "Other unknown entry.",
                "pearl": "Pearl entry.",
                "platinum": None,
            }
        }

        result = self.pokedb.pokemon_reference(reference, "platinum")

        self.assertEqual(result["flavor_text"], "Pearl entry.")
        self.assertEqual(result["flavor_text_version"], "pearl")
        del reference["flavor_text"]["pearl"]
        del reference["flavor_text"]["heartgold"]
        result = self.pokedb.pokemon_reference(reference, None)
        self.assertEqual(result["flavor_text_version"], "aa-unknown")

    def test_reference_effect_text_falls_back_independently_of_key_order(
        self,
    ) -> None:
        pokedb = PokeDBGeneration(
            pokemon_by_id={},
            pokemon_by_name={},
            pokemon_by_species={},
            abilities_by_id={},
            items_by_id={},
            abilities_reference={
                1: {
                    "effect": {
                        "black-2-white-2": "Later effect.",
                        "black-white": "Earlier effect.",
                    }
                }
            },
        )

        result = pokedb.ability_reference(1, "heartgold-soulsilver")

        assert result is not None
        self.assertEqual(result["version"], "black-white")
        self.assertEqual(result["effect"], "Earlier effect.")


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _write_minimal_pokedb(root: Path) -> None:
    _write_json(
        root / "pokemon" / "default" / "1.json",
        {"id": 1, "name": "bulbasaur", "species": "bulbasaur"},
    )
    _write_json(
        root / "pokemon" / "variant" / "10091.json",
        {"id": 10091, "name": "venusaur-mega", "species": "venusaur"},
    )
    _write_json(root / "ability" / "1.json", {"id": 1, "name": "stench"})
    _write_json(root / "item" / "1.json", {"id": 1, "name": "master-ball"})
    _write_json(root / "move" / "1.json", {"id": 1, "name": "pound"})


class PokeDBLoadTests(unittest.TestCase):
    def test_loads_a_well_formed_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_minimal_pokedb(root)

            pokedb = PokeDBGeneration.load(root)

            self.assertEqual(pokedb.pokemon_for_id(1)["species"], "bulbasaur")
            self.assertEqual(pokedb.pokemon_for_name("venusaur-mega")["id"], 10091)
            self.assertEqual(pokedb.pokemon_for_species("bulbasaur")["id"], 1)
            self.assertEqual(pokedb.ability_name(1), "stench")
            self.assertEqual(pokedb.item_name(1), "master-ball")
            self.assertEqual(pokedb.move_name(1), "pound")

    def test_rejects_a_missing_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(DataSourceError, "does not exist"):
                PokeDBGeneration.load(root)

    def test_rejects_an_empty_resource_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_minimal_pokedb(root)
            for path in (root / "ability").glob("*.json"):
                path.unlink()

            with self.assertRaisesRegex(DataSourceError, "no JSON objects"):
                PokeDBGeneration.load(root)

    def test_rejects_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_minimal_pokedb(root)
            (root / "ability" / "broken.json").write_text("not json", encoding="utf-8")

            with self.assertRaisesRegex(DataSourceError, "Invalid PokéDB JSON"):
                PokeDBGeneration.load(root)

    def test_rejects_an_object_missing_its_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_minimal_pokedb(root)
            _write_json(root / "ability" / "2.json", {"name": "no-id"})

            with self.assertRaisesRegex(DataSourceError, "Invalid PokéDB object"):
                PokeDBGeneration.load(root)

    def test_rejects_duplicate_default_pokemon_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_minimal_pokedb(root)
            _write_json(
                root / "pokemon" / "default" / "1-dup.json",
                {"id": 1, "name": "bulbasaur-dup", "species": "bulbasaur-dup"},
            )

            with self.assertRaisesRegex(DataSourceError, "IDs must be unique"):
                PokeDBGeneration.load(root)

    def test_rejects_duplicate_resource_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_minimal_pokedb(root)
            _write_json(
                root / "ability" / "1-dup.json", {"id": 1, "name": "stench-dup"}
            )

            with self.assertRaisesRegex(DataSourceError, "ability IDs must be unique"):
                PokeDBGeneration.load(root)

    def test_rejects_colliding_lookup_keys(self) -> None:
        collisions = {
            "Pokémon name": (
                "pokemon/variant/10092.json",
                {"id": 10092, "name": "bulbasaur", "species": "bulbasaur"},
            ),
            "default Pokémon species": (
                "pokemon/default/2.json",
                {"id": 2, "name": "ivysaur", "species": "bulbasaur"},
            ),
            "item name": ("item/2.json", {"id": 2, "name": "master-ball"}),
            "share a lookup key": ("item/3.json", {"id": 3, "name": "masterball"}),
        }
        for message, (relative, value) in collisions.items():
            with self.subTest(message), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                _write_minimal_pokedb(root)
                _write_json(root / relative, value)

                with self.assertRaisesRegex(DataSourceError, message):
                    PokeDBGeneration.load(root)


class PokeDBLookupMissTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pokedb = PokeDBGeneration(
            pokemon_by_id={},
            pokemon_by_name={},
            pokemon_by_species={},
            abilities_by_id={},
            items_by_id={},
        )

    def test_raises_for_an_unknown_pokemon_id(self) -> None:
        with self.assertRaisesRegex(DataSourceError, "Pokémon ID does not exist"):
            self.pokedb.pokemon_for_id(999)

    def test_raises_for_an_unknown_pokemon_name(self) -> None:
        with self.assertRaisesRegex(DataSourceError, "Pokémon does not exist"):
            self.pokedb.pokemon_for_name("missingno")

    def test_raises_for_an_unknown_species(self) -> None:
        with self.assertRaisesRegex(DataSourceError, "species does not exist"):
            self.pokedb.pokemon_for_species("missingno")

    def test_raises_for_an_unknown_ability_id(self) -> None:
        with self.assertRaisesRegex(DataSourceError, "ability ID does not exist"):
            self.pokedb.ability_name(999)

    def test_ability_id_zero_means_no_ability(self) -> None:
        self.assertIsNone(self.pokedb.ability_name(0))

    def test_raises_for_an_unknown_item_id(self) -> None:
        with self.assertRaisesRegex(DataSourceError, "item ID does not exist"):
            self.pokedb.item_name(999)

    def test_item_id_zero_means_no_item(self) -> None:
        self.assertIsNone(self.pokedb.item_name(0))

    def test_raises_for_an_unknown_move_id(self) -> None:
        with self.assertRaisesRegex(DataSourceError, "move ID does not exist"):
            self.pokedb.move_name(999)

    def test_move_id_zero_means_no_move(self) -> None:
        self.assertIsNone(self.pokedb.move_name(0))


if __name__ == "__main__":
    unittest.main()


class PokeDBPackTests(unittest.TestCase):
    def _pack(self) -> bytes:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_minimal_pokedb(root)
            _write_json(
                root / "pokemon" / "default" / "1.json",
                {
                    "id": 1,
                    "name": "bulbasaur",
                    "species": "bulbasaur",
                    "genus": "Seed Pokémon",
                    "moves": {"tackle": []},
                    "unverified_historical_fields": ["moves"],
                },
            )
            return pack_pokedb(root)

    def test_a_pack_loads_like_its_directory_without_unread_fields(self) -> None:
        pokedb = PokeDBGeneration.load_pack(self._pack())

        bulbasaur = pokedb.pokemon_for_id(1)
        self.assertEqual(bulbasaur["genus"], "Seed Pokémon")
        self.assertNotIn("moves", bulbasaur)
        self.assertNotIn("unverified_historical_fields", bulbasaur)
        self.assertEqual(pokedb.pokemon_for_name("venusaur-mega")["id"], 10091)
        self.assertEqual(pokedb.move_name(1), "pound")

    def test_packing_is_deterministic(self) -> None:
        self.assertEqual(self._pack(), self._pack())

    def test_rejects_data_that_is_not_a_pack(self) -> None:
        with self.assertRaisesRegex(DataSourceError, "Invalid PokéDB pack"):
            PokeDBGeneration.load_pack(b"not a pack")
        with self.assertRaisesRegex(DataSourceError, "Unsupported PokéDB pack"):
            PokeDBGeneration.load_pack(gzip.compress(b'{"schema_version": 99}'))

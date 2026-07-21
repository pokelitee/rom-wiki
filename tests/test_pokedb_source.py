from __future__ import annotations

import unittest

from romwiki.sources import PokeDBGeneration


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
                    "platinum": {
                        "front_default": "https://example.test/platinum.png"
                    }
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
            {"sprites": {"other": {"home": {"front_default": "https://example.test/home.png"}}}}
        )
        without_artwork = self.pokedb.pokemon_portrait(
            {"sprites": {"front_default": "https://example.test/default.png"}}
        )
        rejects_non_https = self.pokedb.pokemon_portrait(
            {"sprites": {"other": {"home": {"front_default": "http://example.test/home.png"}}}}
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
        self.assertEqual(result["base_stats"]["special_attack"], 65)
        self.assertEqual(result["abilities"], ["overgrow"])


if __name__ == "__main__":
    unittest.main()

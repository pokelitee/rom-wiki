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


if __name__ == "__main__":
    unittest.main()

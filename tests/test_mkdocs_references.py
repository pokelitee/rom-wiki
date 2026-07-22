from __future__ import annotations

import unittest

from romwiki.renderers.mkdocs.references import (
    ROUTES,
    ReferenceIndex,
    entity_reference,
)


class RouteResolverTests(unittest.TestCase):
    def test_resolves_markdown_and_published_routes_from_page_depth(self) -> None:
        ability = entity_reference("ability", 65, "Overgrow", "overgrow")

        self.assertEqual(
            ROUTES.markdown_href(ability, "pokemon/bulbasaur.md"),
            "../abilities/overgrow.md",
        )
        self.assertEqual(
            ROUTES.published_href(ability, "pokemon/bulbasaur/"),
            "../../abilities/overgrow/",
        )
        self.assertEqual(
            ROUTES.published_href(ability, "pokemon/"),
            "../abilities/overgrow/",
        )

    def test_serializes_catalog_reference_with_stable_identity(self) -> None:
        pokemon = entity_reference("pokemon", 1, "Bulbasaur", "bulbasaur")

        self.assertEqual(
            ROUTES.catalog_reference(pokemon, "abilities/"),
            {
                "kind": "pokemon",
                "id": 1,
                "label": "Bulbasaur",
                "url": "../pokemon/bulbasaur/",
            },
        )

    def test_keeps_unresolved_reference_as_plain_text(self) -> None:
        unresolved = entity_reference("pokemon", 0, "Unknown", None)

        self.assertEqual(ROUTES.markdown_link(unresolved, "items/test.md"), "Unknown")
        self.assertEqual(ROUTES.html_link(unresolved, "items/test/"), "Unknown")
        self.assertNotIn(
            "url", ROUTES.catalog_reference(unresolved, "items/")
        )

    def test_indexes_dataset_sprite_urls_without_assuming_a_generation(self) -> None:
        index = ReferenceIndex.from_datasets({
            "pokemon": {"records": [{
                "public": True,
                "member": 25,
                "national_dex_id": 25,
                "name": "Pikachu",
                "slug": "pikachu",
                "sprite": {"url": "https://example.test/gen-2/pikachu.png"},
            }]},
            "items": {"records": [{
                "item_id": 17,
                "name": "Potion",
                "slug": "potion",
                "reference": {"sprite_url": "https://example.test/gen-2/potion.png"},
            }]},
        })

        self.assertEqual(
            index.sprite_url("pokemon", 25),
            "https://example.test/gen-2/pikachu.png",
        )
        self.assertEqual(
            index.sprite_url("item", 17),
            "https://example.test/gen-2/potion.png",
        )
        self.assertIsNone(index.sprite_url("item", 999))


if __name__ == "__main__":
    unittest.main()

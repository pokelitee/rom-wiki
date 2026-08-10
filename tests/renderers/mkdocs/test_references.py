from __future__ import annotations

import unittest

from romwiki.renderers.mkdocs.references import (
    ROUTES,
    ReferenceIndex,
    encounter_route_kind,
    entity_reference,
)


class RouteResolverTests(unittest.TestCase):
    def test_selects_encounter_route_family_from_normalized_identity(self) -> None:
        self.assertEqual(encounter_route_kind(7), "encounter")
        self.assertEqual(encounter_route_kind("map-007-spring"), "encounter_variant")

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

    def test_resolves_every_entity_route_in_both_output_contexts(self) -> None:
        cases = (
            ("pokemon", "pikachu", "pikachu.md", "../pikachu/"),
            (
                "ability",
                "overgrow",
                "../abilities/overgrow.md",
                "../../abilities/overgrow/",
            ),
            ("item", "potion", "../items/potion.md", "../../items/potion/"),
            ("move", "tackle", "../moves/tackle.md", "../../moves/tackle/"),
            (
                "location",
                7,
                "../locations/header-007.md",
                "../../locations/header-007/",
            ),
            (
                "trainer",
                7,
                "../trainers/trainer-0007.md",
                "../../trainers/trainer-0007/",
            ),
            (
                "encounter",
                7,
                "../encounters/area-007.md",
                "../../encounters/area-007/",
            ),
            (
                "encounter_variant",
                "map-007-spring",
                "../encounters/map-007-spring.md",
                "../../encounters/map-007-spring/",
            ),
        )
        for kind, route_key, markdown_href, published_href in cases:
            with self.subTest(kind=kind):
                reference = entity_reference(kind, route_key, "Label", route_key)
                self.assertEqual(
                    ROUTES.markdown_href(reference, "pokemon/bulbasaur.md"),
                    markdown_href,
                )
                self.assertEqual(
                    ROUTES.published_href(reference, "pokemon/bulbasaur/"),
                    published_href,
                )

    def test_keeps_type_references_as_plain_text(self) -> None:
        type_reference = entity_reference("type", "fire", "Fire", "fire")

        self.assertEqual(
            ROUTES.markdown_link(type_reference, "pokemon/charizard.md"),
            "Fire",
        )
        self.assertEqual(
            ROUTES.html_link(type_reference, "pokemon/charizard/"),
            "Fire",
        )
        self.assertNotIn(
            "url",
            ROUTES.catalog_reference(type_reference, "pokemon/"),
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
        self.assertNotIn("url", ROUTES.catalog_reference(unresolved, "items/"))

    def test_rejects_mixed_markdown_and_published_link_contexts(self) -> None:
        ability = entity_reference("ability", 65, "Overgrow", "overgrow")

        with self.assertRaisesRegex(ValueError, "Markdown link source"):
            ROUTES.markdown_href(ability, "pokemon/bulbasaur/")
        with self.assertRaisesRegex(ValueError, "Published link source"):
            ROUTES.published_href(ability, "pokemon/bulbasaur.md")

    def test_indexes_dataset_sprite_urls_without_assuming_a_generation(self) -> None:
        index = ReferenceIndex.from_datasets(
            {
                "pokemon": {
                    "records": [
                        {
                            "public": True,
                            "member": 25,
                            "national_dex_id": 25,
                            "name": "Pikachu",
                            "slug": "pikachu",
                            "sprite": {"url": "https://example.test/gen-2/pikachu.png"},
                        }
                    ]
                },
                "items": {
                    "records": [
                        {
                            "item_id": 17,
                            "name": "Potion",
                            "slug": "potion",
                            "reference": {
                                "sprite_url": "https://example.test/gen-2/potion.png"
                            },
                        }
                    ]
                },
            }
        )

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

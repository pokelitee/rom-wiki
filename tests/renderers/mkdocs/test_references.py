from __future__ import annotations

import unittest

import markdown

from romwiki.renderers.mkdocs.references import (
    ROUTES,
    ReferenceIndex,
    encounter_route_kind,
    entity_reference,
    escape_markdown,
)


class RouteResolverTests(unittest.TestCase):
    def test_selects_encounter_route_family_from_normalized_identity(self) -> None:
        self.assertEqual(encounter_route_kind(7), "encounter")
        self.assertEqual(encounter_route_kind("map-007"), "encounter_variant")
        self.assertEqual(
            encounter_route_kind("header-445#hidden-grotto-00"),
            "encounter_location",
        )

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
                "map-007",
                "../encounters/map-007.md",
                "../../encounters/map-007/",
            ),
            (
                "encounter_variant",
                "safari-zone#plains",
                "../encounters/safari-zone.md#plains",
                "../../encounters/safari-zone/#plains",
            ),
            (
                "encounter_location",
                "header-445#hidden-grotto-00",
                "../locations/header-445.md#hidden-grotto-00",
                "../../locations/header-445/#hidden-grotto-00",
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

    def test_markdown_labels_render_rom_text_without_raw_html(self) -> None:
        hostile = "</td><img src=x onerror=alert(1)> [x] | y"
        linked = entity_reference("pokemon", 1, hostile, "bulbasaur")
        unresolved = entity_reference("pokemon", 0, hostile, None)
        expected = "&lt;/td&gt;&lt;img src=x onerror=alert(1)&gt; \\[x\\] &#124; y"

        self.assertEqual(escape_markdown(hostile), expected)
        self.assertEqual(
            ROUTES.markdown_link(linked, "items/test.md"),
            f"[{expected}](../pokemon/bulbasaur.md)",
        )
        self.assertEqual(ROUTES.markdown_link(unresolved, "items/test.md"), expected)

    def test_markdown_labels_render_ordinary_names_unchanged(self) -> None:
        extensions = ["attr_list", "md_in_html", "tables"]
        for name in ("Farfetch'd", "Nidoran♀", 'Say "Hi"', "Backers Masa & Yas"):
            with self.subTest(name=name):
                self.assertEqual(
                    markdown.markdown(
                        f"| A |\n| - |\n| {escape_markdown(name)} |",
                        extensions=extensions,
                    ),
                    markdown.markdown(
                        f"| A |\n| - |\n| {name} |", extensions=extensions
                    ),
                )

    def test_resolves_only_matching_labels_when_requested(self) -> None:
        index = ReferenceIndex(
            [entity_reference("item", 110, "Link Cable", "link-cable")]
        )

        self.assertEqual(
            index.resolve_matching("item", 110, "Link Cable").route_key,
            "link-cable",
        )
        self.assertIsNone(index.resolve_matching("item", 110, "Oval Stone").route_key)

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

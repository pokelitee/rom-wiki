from __future__ import annotations

import unittest

from romwiki.renderers.mkdocs.references import ROUTES, entity_reference


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


if __name__ == "__main__":
    unittest.main()

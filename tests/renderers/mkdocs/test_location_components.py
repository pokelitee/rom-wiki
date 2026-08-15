from __future__ import annotations

import unittest

import markdown

from romwiki.renderers.mkdocs.location_components import (
    append_items,
    append_trainers,
    append_warps,
    item_event_coverage_notice,
)


class LocationComponentContractTests(unittest.TestCase):
    def test_renders_trainers_as_a_compact_reference_table(self) -> None:
        lines: list[str] = []

        append_trainers(
            lines,
            [
                {
                    "trainer_id": 246,
                    "class_name": "Leader",
                    "name": "Roark",
                    "source": "map-script",
                }
            ],
            "locations/header-045.md",
        )

        page = "\n".join(lines)
        self.assertIn("| Trainer | ID | Trigger |", page)
        self.assertIn(
            "| [Leader Roark](../trainers/trainer-0246.md) | `trainer-0246` | Map Script |",
            page,
        )

    def test_summarizes_unresolved_item_events_for_the_location_index(self) -> None:
        notice = item_event_coverage_notice(
            [
                {
                    "items": [
                        {"name": "Potion", "x": 0, "z": 0},
                        {"name": "Antidote", "x": 5, "z": 8},
                    ]
                },
                {"items": [{"name": "???", "x": 2, "z": 3}]},
            ]
        )

        self.assertIn("2 ROM item-event records", notice)
        self.assertIn("not asserted to be reachable pickups", notice)

    def test_flags_suspicious_item_event_records(self) -> None:
        lines: list[str] = []

        append_items(
            lines,
            [
                {
                    "event_index": 7,
                    "kind": "visible",
                    "item_id": 17,
                    "name": "Potion",
                    "x": 0,
                    "z": 0,
                }
            ],
            "locations/header-001.md",
            None,
        )

        page = "\n".join(lines)
        self.assertIn("not NPC gifts, bundled rewards", page)
        self.assertIn('!!! warning "Suspicious ROM item records"', page)
        self.assertIn("Potion (event 7)", page)

    def test_empty_warp_section_does_not_change_the_document(self) -> None:
        lines = ["# Location", ""]

        append_warps(lines, [], "locations/header-001.md")

        self.assertEqual(lines, ["# Location", ""])

    def test_dynamic_warp_table_has_stable_markdown_structure(self) -> None:
        lines: list[str] = []

        append_warps(
            lines,
            [
                {
                    "index": 0,
                    "x": 488,
                    "z": 824,
                    "destination_header_id": None,
                    "destination_warp_id": None,
                    "destination_name": None,
                    "destination_section_name": None,
                    "destination_internal_name": None,
                    "destination_warp_exists": None,
                    "dynamic": True,
                }
            ],
            "locations/header-150.md",
        )

        self.assertEqual(
            lines,
            [
                "## Warps",
                "",
                "Dynamic destination means the ROM does not store one fixed "
                "destination header or destination warp for that row. The em "
                "dashes are explicit unavailable values, not missing cells.",
                "",
                "| Warp | Position | To | Section | Map ID | Arrival |",
                "| ---: | -------- | -- | ------- | ------ | ------- |",
                "| 0 | (488, 824) | Dynamic destination | — | — | — |",
                "",
            ],
        )
        rendered = markdown.markdown("\n".join(lines), extensions=["tables"])
        self.assertIn("<h2>Warps</h2>", rendered)
        self.assertIn("<table>", rendered)
        self.assertEqual(rendered.count("<td"), 6)


if __name__ == "__main__":
    unittest.main()

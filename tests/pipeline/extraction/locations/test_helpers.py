from __future__ import annotations

import unittest
from types import SimpleNamespace

from romwiki.engines.registry import get_engine
from romwiki.pipeline.extraction.locations.helpers import extract_event_map_items


class LocationItemTests(unittest.TestCase):
    def test_extracts_standard_visible_and_hidden_item_scripts(self) -> None:
        names = [f"Item {item_id}" for item_id in range(100)]
        events = SimpleNamespace(
            objects=(
                SimpleNamespace(
                    index=3,
                    graphics_id=87,
                    script_id=7017,
                    x=8,
                    z=11,
                    y=0,
                    hidden_flag=400,
                ),
                SimpleNamespace(
                    index=4,
                    graphics_id=87,
                    script_id=7000,
                    x=1,
                    z=1,
                    y=0,
                    hidden_flag=0,
                ),
                # An ordinary NPC reusing the item-ball sprite for flavor
                # (e.g. a glinting-light dialogue trigger), not a real item
                # ball -- its `script_id` is a small local script index, well
                # below the item-ball band, so it must not be treated as an
                # unresolved pickup at all.
                SimpleNamespace(
                    index=5,
                    graphics_id=87,
                    script_id=3,
                    x=2,
                    z=2,
                    y=0,
                    hidden_flag=0,
                ),
            ),
            backgrounds=(
                SimpleNamespace(
                    index=1,
                    script_id=8081,
                    event_type=2,
                    x=12,
                    z=5,
                    y=0,
                ),
            ),
        )

        scan = extract_event_map_items(
            get_engine("gen4_platinum").locations, events, tuple(names)
        )
        items = scan.items

        self.assertEqual(
            [(item.kind, item.item_id) for item in items],
            [
                ("visible", 17),
                ("hidden", 81),
            ],
        )
        self.assertEqual(items[0].hidden_flag, 400)
        self.assertIsNone(items[1].hidden_flag)
        # The second object event has the item-ball sprite and a `script_id`
        # in the item-ball band, but it resolves to item 0 (the "no item"
        # sentinel) -- a real pickup the extractor couldn't identify, which
        # should be counted rather than dropped silently.
        self.assertEqual(scan.unresolved_visible_count, 1)
        self.assertEqual(scan.unresolved_hidden_count, 0)


if __name__ == "__main__":
    unittest.main()

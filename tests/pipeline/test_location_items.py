from __future__ import annotations

import unittest
from types import SimpleNamespace

from romwiki.pipeline.locations import _extract_gen4_location_items


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
                    script_id=7,
                    x=1,
                    z=1,
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

        items = _extract_gen4_location_items(events, tuple(names))

        self.assertEqual(
            [(item.kind, item.item_id) for item in items],
            [
                ("visible", 17),
                ("hidden", 81),
            ],
        )
        self.assertEqual(items[0].hidden_flag, 400)
        self.assertIsNone(items[1].hidden_flag)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

from romwiki.renderers.mkdocs.trainers import _append_ai_battle_items, _party_cards


class TrainerRenderingTests(unittest.TestCase):
    def test_groups_ai_battle_item_slots_and_renders_icons(self) -> None:
        record = {
            "ai_battle_items": [
                {
                    "id": 23,
                    "name": "Full Restore",
                    "slug": "full-restore",
                    "sprite_url": "https://example.test/full-restore.png",
                },
                {
                    "id": 23,
                    "name": "Full Restore",
                    "slug": "full-restore",
                    "sprite_url": "https://example.test/full-restore.png",
                },
            ]
        }
        lines: list[str] = []

        _append_ai_battle_items(lines, record, "trainers/trainer-0005.md")
        page = "\n".join(lines)

        self.assertEqual(page.count("[Full Restore](../items/full-restore.md)"), 1)
        self.assertIn('src="https://example.test/full-restore.png"', page)
        self.assertIn("| 2 |", page)

    def test_renders_contextual_empty_state(self) -> None:
        lines: list[str] = []

        _append_ai_battle_items(lines, {"ai_battle_items": []}, "trainers/test.md")

        self.assertIn("No AI battle items.", lines)

    def test_numbers_explicit_moves_in_rom_order(self) -> None:
        party = [_party_member(["tackle", "growl"])]

        page = "\n".join(_party_cards(party, "trainers/trainer-0001/"))

        self.assertIn('<ol class="rw-party-card__moves"', page)
        self.assertLess(page.index("Tackle"), page.index("Growl"))
        self.assertNotIn("default level-up moves", page)

    def test_formats_default_moves_without_a_numbered_slot(self) -> None:
        page = "\n".join(
            _party_cards([_party_member([])], "trainers/trainer-0001/")
        )

        self.assertNotIn('<ol class="rw-party-card__moves"', page)
        self.assertIn("Uses default level-up moves.", page)


def _party_member(moves: list[str]) -> dict[str, object]:
    return {
        "level": 5,
        "held_item": None,
        "pokemon": {
            "id": 1,
            "name": "Bulbasaur",
            "slug": "bulbasaur",
            "sprite": None,
        },
        "moves": [{"id": index, "name": name} for index, name in enumerate(moves)],
    }


if __name__ == "__main__":
    unittest.main()

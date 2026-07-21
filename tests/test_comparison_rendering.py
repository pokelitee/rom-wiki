from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from romwiki.renderers.mkdocs.comparisons import (
    comparison_section,
    render_changes_pages,
)
from romwiki.renderers.mkdocs.references import ReferenceIndex, entity_reference


class ComparisonRenderingTests(unittest.TestCase):
    def test_hack_only_overview_is_explicit_and_prunes_stale_snapshots(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stale = root / "changes" / "moves" / "stale.md"
            stale.parent.mkdir(parents=True)
            stale.write_text("stale", encoding="utf-8")

            count = render_changes_pages({}, root)

            overview = (root / "changes" / "index.md").read_text(encoding="utf-8")
            self.assertEqual(count, 1)
            self.assertIn("without a clean-ROM comparison", overview)
            self.assertFalse(stale.exists())

    def test_renders_explicit_unchanged_and_changed_sections(self) -> None:
        unchanged = comparison_section(
            {"status": "unchanged", "changes": []}, "Pokémon Platinum"
        )
        changed = comparison_section(
            {
                "status": "changed",
                "changes": [
                    {"label": "Power", "before": 40, "after": 60}
                ],
            },
            "Pokémon Platinum",
        )

        self.assertIn("Verified unchanged", "\n".join(unchanged))
        self.assertIn("| Power | 40 → 60 |", "\n".join(changed))

    def test_complex_changes_render_only_exact_list_deltas(self) -> None:
        section = comparison_section(
            {
                "status": "changed",
                "changes": [
                    {
                        "label": "Moves",
                        "before": [{"id": 1}, {"id": 2}],
                        "after": [{"id": 2}, {"id": 3}],
                    }
                ],
            },
            "Base",
        )
        value = "\n".join(section)

        self.assertIn('{&quot;id&quot;:1}', value)
        self.assertIn('{&quot;id&quot;:3}', value)
        self.assertNotIn('{&quot;id&quot;:2}', value)

    def test_pokemon_changes_use_readable_field_specific_summaries(self) -> None:
        references = ReferenceIndex(
            [
                entity_reference(
                    "move", 363, "Natural Gift", "natural-gift"
                )
            ]
        )
        section = comparison_section(
            {
                "kind": "pokemon",
                "status": "changed",
                "changes": [
                    {
                        "field": "abilities",
                        "label": "Abilities",
                        "before": [
                            {"id": 65, "name": "Overgrow", "slug": "overgrow"},
                            {"id": 0, "name": None},
                        ],
                        "after": [
                            {
                                "id": 34,
                                "name": "Chlorophyll",
                                "slug": "chlorophyll",
                            },
                            {"id": 65, "name": "Overgrow", "slug": "overgrow"},
                        ],
                    },
                    {
                        "field": "machines",
                        "label": "Machines",
                        "before": [
                            {
                                "id": 83,
                                "name": "TM83",
                                "move": {
                                    "id": 363,
                                    "name": "Natural Gift",
                                    "slug": "naturalgift",
                                },
                            }
                        ],
                        "after": [],
                    },
                ],
            },
            "Platinum",
            "pokemon/bulbasaur.md",
            references,
        )
        value = "\n".join(section)

        self.assertIn(">Overgrow</a>", value)
        self.assertIn(">Chlorophyll</a>", value)
        self.assertIn(">Natural Gift</a>: Compatible → Not compatible", value)
        self.assertIn('href="../../abilities/overgrow/"', value)
        self.assertIn('href="../../moves/natural-gift/"', value)
        self.assertNotIn("{&quot;id&quot;", value)

    def test_generic_summary_accepts_string_evolution_methods(self) -> None:
        section = comparison_section(
            {
                "kind": "items",
                "status": "changed",
                "changes": [
                    {
                        "field": "evolutions",
                        "label": "Evolutions",
                        "before": [],
                        "after": [
                            {
                                "target": {"id": 2, "name": "Ivysaur"},
                                "method": "use-item",
                            }
                        ],
                    }
                ],
            },
            "Platinum",
        )

        self.assertIn("Ivysaur — use-item", "\n".join(section))

    def test_renders_overview_and_removed_snapshot(self) -> None:
        comparison = {
            "kind": "moves",
            "game": "hack",
            "baseline": "base",
            "counts": {"unchanged": 0, "changed": 1, "added": 0, "removed": 1},
            "records": [
                {
                    "key": 1,
                    "label": "Pound",
                    "slug": "pound",
                    "status": "changed",
                    "detail_available": True,
                    "changes": [
                        {"label": "Power", "before": 40, "after": 60}
                    ],
                },
                {
                    "key": 2,
                    "label": "Karate Chop",
                    "slug": "karate-chop",
                    "status": "removed",
                    "detail_available": False,
                    "changes": [],
                    "baseline_record": {"power": 50},
                },
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            count = render_changes_pages({"moves": comparison}, root)

            overview = (root / "changes" / "index.md").read_text(encoding="utf-8")
            snapshot = root / "changes" / "moves" / "karate-chop.md"
            self.assertEqual(count, 2)
            self.assertIn("../moves/pound.md", overview)
            self.assertTrue(snapshot.is_file())
            self.assertIn("Removed in this hack", snapshot.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

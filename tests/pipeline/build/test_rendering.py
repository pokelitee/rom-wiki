from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from romwiki.pipeline.build.rendering import (
    comparison_workflow_kind,
    current_relationship_datasets,
    dataset_output,
    load_comparisons,
    render_game_build,
    render_section_build,
    render_version_family_build,
)
from romwiki.util.errors import LocalConfigError


class DatasetOutputPathTests(unittest.TestCase):
    def test_locations_use_the_raw_filename(self) -> None:
        self.assertEqual(
            dataset_output(Path("build/data/game"), "locations"),
            Path("build/data/game/locations/raw.json"),
        )

    def test_every_other_kind_uses_the_enriched_filename(self) -> None:
        for kind in (
            "pokemon",
            "abilities",
            "moves",
            "items",
            "encounters",
            "trainers",
        ):
            self.assertEqual(
                dataset_output(Path("build/data/game"), kind),
                Path(f"build/data/game/{kind}/enriched.json"),
            )


class FocusedSectionBuildTests(unittest.TestCase):
    def test_encounter_build_includes_location_relationships(self) -> None:
        encounters = {
            "game": "test",
            "records": [
                {
                    "area_id": 8,
                    "map_index": 3,
                    "season": "spring",
                    "name": "Route 1",
                }
            ],
        }
        locations = {
            "game": "test",
            "records": [
                {
                    "header_id": 6,
                    "name": "Route 1",
                    "encounter_map_index": 3,
                }
            ],
        }
        pokemon = {"game": "test", "records": []}
        current = SimpleNamespace(
            profile=SimpleNamespace(id="test"),
            encounters=lambda: encounters,
            locations=lambda: locations,
            pokemon=lambda: pokemon,
        )
        workflow = SimpleNamespace(
            current=current,
            build=lambda kind: SimpleNamespace(
                current=encounters,
                comparison=None,
            ),
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (
                patch("romwiki.pipeline.build.rendering.write_section") as write,
                patch("romwiki.pipeline.build.rendering.render_changes_pages"),
            ):
                render_section_build(
                    "encounters",
                    workflow,
                    data_root=root / "data",
                    wiki_root=root / "wiki",
                    wiki_output=root / "wiki" / "encounters",
                    data_output=root / "data" / "encounters" / "enriched.json",
                )

        context = write.call_args.args[5]
        self.assertEqual(
            context.relationship_index.encounter_locations["map-003"][0].header_id,
            6,
        )
        self.assertIsNotNone(context.reference_index)

    def test_changes_follow_full_build_section_and_field_order(self) -> None:
        items = {"game": "test", "records": []}
        pokemon = {"game": "test", "records": []}
        current = SimpleNamespace(
            profile=SimpleNamespace(id="test"),
            pokemon=lambda: pokemon,
            locations=lambda: None,
        )
        comparison = {"kind": "items", "zeta": 1, "alpha": 2}
        workflow = SimpleNamespace(
            current=current,
            build=lambda kind: SimpleNamespace(current=items, comparison=comparison),
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stored = root / "data" / "comparisons"
            stored.mkdir(parents=True)
            for kind in ("trainers", "pokemon"):
                (stored / f"{kind}.json").write_text(
                    json.dumps({"kind": kind}), encoding="utf-8"
                )
            with (
                patch("romwiki.pipeline.build.rendering.write_public_dataset"),
                patch.dict(
                    "romwiki.pipeline.build.rendering._SECTION_RENDERERS",
                    {"items": lambda *_args: 0},
                ),
                patch(
                    "romwiki.pipeline.build.rendering.render_changes_pages"
                ) as render_changes,
            ):
                render_section_build(
                    "items", workflow, data_root=root / "data", wiki_root=root / "wiki"
                )
            written = (stored / "items.json").read_text(encoding="utf-8")

        self.assertEqual(
            list(render_changes.call_args.args[0]), ["pokemon", "items", "trainers"]
        )
        self.assertEqual(list(json.loads(written)), ["kind", "zeta", "alpha"])


class RelationshipDatasetTests(unittest.TestCase):
    def test_collects_companions_and_omits_unsupported_datasets(self) -> None:
        datasets = {
            kind: {"game": "test", "records": []}
            for kind in ("pokemon", "encounters", "items")
        }
        context = SimpleNamespace(
            profile=SimpleNamespace(
                layout={
                    "personal": "personal",
                    "moves": "moves",
                    "item_data": "items",
                    "messages": "messages",
                    "encounters": "encounters",
                },
                parameters={},
            ),
            pokemon=lambda: datasets["pokemon"],
            encounters=lambda: datasets["encounters"],
            trainers=lambda: None,
            locations=lambda: None,
            items=lambda: datasets["items"],
            trades=lambda: None,
        )

        self.assertEqual(
            current_relationship_datasets(context),
            datasets,
        )


class OptionalSectionBuildTests(unittest.TestCase):
    def _render_full_game(self, kinds: tuple[str, ...]) -> list[tuple]:
        builds = {
            kind: SimpleNamespace(
                current=_build_dataset(kind, "partial"),
                comparison=None,
            )
            for kind in kinds
        }
        current = SimpleNamespace(
            profile=SimpleNamespace(id="partial"),
            trades=lambda: None,
        )
        workflow = SimpleNamespace(current=current, build_all=lambda: builds)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (
                patch(
                    "romwiki.pipeline.build.rendering.build_type_dataset",
                    return_value=_build_dataset("types", "partial"),
                ),
                patch("romwiki.pipeline.build.rendering.write_type_section"),
                patch("romwiki.pipeline.build.rendering.write_section") as write,
                patch(
                    "romwiki.pipeline.build.rendering.render_changes_pages",
                    return_value=0,
                ),
            ):
                render_game_build(
                    workflow,
                    data_root=root / "data" / "partial",
                    wiki_root=root / "wiki",
                )
        return [call.args for call in write.call_args_list]

    def test_full_game_build_writes_only_enabled_datasets(self) -> None:
        kinds = ("pokemon", "abilities", "moves", "items", "encounters")

        calls = self._render_full_game(kinds)

        self.assertEqual([args[0] for args in calls], list(kinds))
        self.assertEqual(calls[0][5].move_dataset, _build_dataset("moves", "partial"))

    def test_full_game_build_without_moves_renders_without_move_links(self) -> None:
        kinds = ("pokemon", "abilities")

        calls = self._render_full_game(kinds)

        self.assertEqual([args[0] for args in calls], list(kinds))
        self.assertIsNone(calls[0][5].move_dataset)

    def test_version_family_rejects_mismatched_optional_sections(self) -> None:
        partial = _section_profile("partial")
        complete = _section_profile("complete", optional=True)
        workflows = {
            "one": SimpleNamespace(current=SimpleNamespace(profile=partial)),
            "two": SimpleNamespace(current=SimpleNamespace(profile=complete)),
        }

        with self.assertRaisesRegex(
            LocalConfigError,
            "different dataset sections.*one omits locations, trainers",
        ):
            render_version_family_build(
                "test-family",
                workflows,
                ("one", "two"),
                data_root=Path("data"),
                wiki_root=Path("wiki"),
            )

    def test_version_family_rejects_workflows_for_other_versions(self) -> None:
        workflows = {"one": SimpleNamespace(), "three": SimpleNamespace()}

        with self.assertRaisesRegex(LocalConfigError, "do not match"):
            render_version_family_build(
                "test-family",
                workflows,
                ("one", "two"),
                data_root=Path("data"),
                wiki_root=Path("wiki"),
            )


class ComparisonWorkflowKindTests(unittest.TestCase):
    def test_wild_encounters_maps_to_the_encounters_workflow_key(self) -> None:
        self.assertEqual(comparison_workflow_kind("wild_encounters"), "encounters")

    def test_every_other_kind_passes_through_unchanged(self) -> None:
        for kind in ("pokemon", "abilities", "moves", "items", "trainers", "locations"):
            self.assertEqual(comparison_workflow_kind(kind), kind)


class LoadComparisonsTests(unittest.TestCase):
    def test_missing_directory_yields_no_comparisons(self) -> None:
        self.assertEqual(load_comparisons(Path("/no/such/comparisons/dir")), {})

    def test_reads_and_reindexes_comparison_files_by_workflow_kind(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "wild_encounters.json").write_text(
                json.dumps({"kind": "wild_encounters", "counts": {}}),
                encoding="utf-8",
            )
            (root / "pokemon.json").write_text(
                json.dumps({"kind": "pokemon", "counts": {}}),
                encoding="utf-8",
            )

            comparisons = load_comparisons(root)

        self.assertEqual(set(comparisons), {"encounters", "pokemon"})
        self.assertEqual(comparisons["encounters"]["kind"], "wild_encounters")

    def test_skips_malformed_or_non_comparison_json_files_with_warnings(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "broken.json").write_text("not json", encoding="utf-8")
            (root / "unrelated.json").write_text(
                json.dumps([1, 2, 3]), encoding="utf-8"
            )
            (root / "pokemon.json").write_text(
                json.dumps({"kind": "pokemon", "counts": {}}),
                encoding="utf-8",
            )

            with self.assertLogs("romwiki", level="WARNING") as logs:
                comparisons = load_comparisons(root)

        self.assertEqual(set(comparisons), {"pokemon"})
        messages = "\n".join(logs.output)
        self.assertEqual(len(logs.output), 2)
        self.assertIn("broken.json: it cannot be read", messages)
        self.assertIn("unrelated.json: it is not a dataset comparison", messages)


def _build_dataset(kind: str, game: str) -> dict:
    return {
        "schema_version": 1,
        "dataset": "wild_encounters" if kind == "encounters" else kind,
        "game": game,
        "source": {"rom_sha256": game},
        "records": [],
    }


def _section_profile(profile_id: str, *, optional: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        id=profile_id,
        parameters={},
        layout={
            "personal": "personal",
            "messages": "messages",
            "moves": "moves",
            "item_data": "items",
            "encounters": "encounters",
            **(
                {
                    "trainer_data": "trainers",
                    "trainer_parties": "parties",
                    "map_headers": "headers",
                }
                if optional
                else {}
            ),
        },
    )


if __name__ == "__main__":
    unittest.main()

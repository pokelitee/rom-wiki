from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from romwiki.pipeline.build.outputs import (
    dataset_output,
    write_game_build,
    write_section_build,
    write_version_family_build,
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


class GameBuildOutputTests(unittest.TestCase):
    def test_full_game_build_writes_only_enabled_datasets_and_exports(self) -> None:
        kinds = ("pokemon", "abilities", "moves", "items", "encounters")
        builds = {
            kind: SimpleNamespace(
                current=_build_dataset(kind, "partial"),
                comparison=None,
            )
            for kind in kinds
        }
        workflow = SimpleNamespace(
            current=SimpleNamespace(profile=SimpleNamespace(id="partial")),
            build_all=lambda: builds,
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_root = root / "data" / "partial"
            wiki_root = root / "wiki"
            stale_export = wiki_root / "data" / "trainers.json.gz"
            stale_export.parent.mkdir(parents=True)
            stale_export.write_bytes(b"")
            stale_comparison = data_root / "comparisons" / "trainers.json"
            stale_comparison.parent.mkdir(parents=True)
            stale_comparison.write_text("{}", encoding="utf-8")
            with patch(
                "romwiki.pipeline.build.outputs.build_type_dataset",
                return_value=_build_dataset("types", "partial"),
            ):
                write_game_build(workflow, data_root=data_root, wiki_root=wiki_root)

            datasets = sorted(
                path.parent.name for path in data_root.glob("*/enriched.json")
            )
            exports = sorted(
                path.name for path in (wiki_root / "data").glob("*.json.gz")
            )
            manifest = json.loads(
                (wiki_root / "data" / "manifest.json").read_text(encoding="utf-8")
            )
            stale_comparison_exists = stale_comparison.exists()

        self.assertEqual(datasets, sorted((*kinds, "types")))
        self.assertEqual(
            exports, sorted(f"{kind}.json.gz" for kind in (*kinds, "types"))
        )
        self.assertEqual(manifest["game"], "partial")
        self.assertFalse(stale_comparison_exists)

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
            write_version_family_build(
                "test-family",
                workflows,
                ("one", "two"),
                data_root=Path("data"),
                wiki_root=Path("wiki"),
            )

    def test_version_family_rejects_workflows_for_other_versions(self) -> None:
        workflows = {"one": SimpleNamespace(), "three": SimpleNamespace()}

        with self.assertRaisesRegex(LocalConfigError, "do not match"):
            write_version_family_build(
                "test-family",
                workflows,
                ("one", "two"),
                data_root=Path("data"),
                wiki_root=Path("wiki"),
            )


class SectionBuildOutputTests(unittest.TestCase):
    def test_section_build_keeps_comparison_field_order(self) -> None:
        comparison = {"kind": "items", "zeta": 1, "alpha": 2}
        workflow = SimpleNamespace(
            current=SimpleNamespace(profile=SimpleNamespace(id="test")),
            build=lambda kind: SimpleNamespace(
                current=_build_dataset(kind, "test"), comparison=comparison
            ),
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_section_build(
                "items", workflow, data_root=root / "data", wiki_root=root / "wiki"
            )
            written = (root / "data" / "comparisons" / "items.json").read_text(
                encoding="utf-8"
            )
            exported = (root / "wiki" / "data" / "items.json.gz").is_file()

        self.assertEqual(list(json.loads(written)), ["kind", "zeta", "alpha"])
        self.assertTrue(exported)

    def test_section_build_without_comparison_removes_a_stale_one(self) -> None:
        workflow = SimpleNamespace(
            current=SimpleNamespace(profile=SimpleNamespace(id="test")),
            build=lambda kind: SimpleNamespace(
                current=_build_dataset(kind, "test"), comparison=None
            ),
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stale = root / "data" / "comparisons" / "moves.json"
            stale.parent.mkdir(parents=True)
            stale.write_text("{}", encoding="utf-8")
            write_section_build(
                "moves", workflow, data_root=root / "data", wiki_root=root / "wiki"
            )
            stale_exists = stale.exists()
            written = (root / "data" / "moves" / "enriched.json").is_file()

        self.assertFalse(stale_exists)
        self.assertTrue(written)


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

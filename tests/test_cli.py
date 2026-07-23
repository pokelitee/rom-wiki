from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from romwiki.cli import (
    _comparison_workflow_kind,
    _dataset_output,
    _load_comparisons,
    main,
)


class MainErrorHandlingTests(unittest.TestCase):
    def test_a_rom_wiki_error_is_reported_and_exits_nonzero(self) -> None:
        exit_code = main(["inspect", "/no/such/rom.nds"])

        self.assertEqual(exit_code, 2)

    def test_an_unknown_command_is_rejected_by_argparse(self) -> None:
        with self.assertRaises(SystemExit):
            main(["not-a-real-command"])

    def test_inspect_prints_json_for_a_matched_profile(self) -> None:
        rom_path = Path(".local/roms/Pokemon - Renegade Platinum.nds")
        if not rom_path.is_file():
            self.skipTest("local ROM fixture is not available in this environment")

        exit_code = main(["inspect", str(rom_path), "--json"])

        self.assertEqual(exit_code, 0)


class DatasetOutputPathTests(unittest.TestCase):
    def test_locations_use_the_raw_filename(self) -> None:
        self.assertEqual(
            _dataset_output(Path("build/data/game"), "locations"),
            Path("build/data/game/locations/raw.json"),
        )

    def test_every_other_kind_uses_the_enriched_filename(self) -> None:
        for kind in ("pokemon", "abilities", "moves", "items", "encounters", "trainers"):
            self.assertEqual(
                _dataset_output(Path("build/data/game"), kind),
                Path(f"build/data/game/{kind}/enriched.json"),
            )


class ComparisonWorkflowKindTests(unittest.TestCase):
    def test_wild_encounters_maps_to_the_encounters_workflow_key(self) -> None:
        self.assertEqual(_comparison_workflow_kind("wild_encounters"), "encounters")

    def test_every_other_kind_passes_through_unchanged(self) -> None:
        for kind in ("pokemon", "abilities", "moves", "items", "trainers", "locations"):
            self.assertEqual(_comparison_workflow_kind(kind), kind)


class LoadComparisonsTests(unittest.TestCase):
    def test_missing_directory_yields_no_comparisons(self) -> None:
        self.assertEqual(_load_comparisons(Path("/no/such/comparisons/dir")), {})

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

            comparisons = _load_comparisons(root)

        self.assertEqual(set(comparisons), {"encounters", "pokemon"})
        self.assertEqual(comparisons["encounters"]["kind"], "wild_encounters")

    def test_ignores_malformed_or_non_comparison_json_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "broken.json").write_text("not json", encoding="utf-8")
            (root / "unrelated.json").write_text(
                json.dumps([1, 2, 3]), encoding="utf-8"
            )

            comparisons = _load_comparisons(root)

        self.assertEqual(comparisons, {})


if __name__ == "__main__":
    unittest.main()

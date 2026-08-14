from __future__ import annotations

import unittest

from romwiki.pipeline.build.fingerprint import extraction_source_files


class ExtractionSourceFilesTests(unittest.TestCase):
    def test_scopes_dependencies_to_the_selected_engine(self) -> None:
        files = extraction_source_files(
            "gen4_hgss", "romwiki.pipeline.extraction.moves"
        )

        self.assertTrue(any(path.startswith("engines/gen4/hgss/") for path in files))
        self.assertFalse(any(path.startswith("engines/gen4/dppt/") for path in files))
        self.assertFalse(any(path.startswith("engines/gen5/") for path in files))
        self.assertNotIn("engines/registry.py", files)

    def test_includes_overlay_fallback_engine_dependencies(self) -> None:
        files = extraction_source_files(
            "gen5_b2w2", "romwiki.pipeline.extraction.items"
        )

        self.assertTrue(any(path.startswith("engines/gen5/b2w2/") for path in files))
        self.assertTrue(any(path.startswith("engines/gen5/bw/") for path in files))

    def test_scopes_dependencies_to_the_selected_extractor(self) -> None:
        files = extraction_source_files(
            "gen4_hgss", "romwiki.pipeline.extraction.moves"
        )

        self.assertIn("pipeline/extraction/moves.py", files)
        self.assertNotIn("pipeline/extraction/locations/dispatcher.py", files)

    def test_includes_split_location_strategy_dependencies(self) -> None:
        files = extraction_source_files(
            "gen4_hgss", "romwiki.pipeline.extraction.locations.dispatcher"
        )

        self.assertIn("pipeline/extraction/locations/arm9_encounter_map.py", files)
        self.assertIn("pipeline/extraction/locations/helpers.py", files)

        dppt_files = extraction_source_files(
            "gen4_dppt", "romwiki.pipeline.extraction.locations.dispatcher"
        )
        self.assertIn("pipeline/extraction/locations/arm9_event_map.py", dppt_files)
        self.assertIn("pipeline/extraction/locations/helpers.py", dppt_files)

        gen5_files = extraction_source_files(
            "gen5_bw", "romwiki.pipeline.extraction.locations.dispatcher"
        )
        self.assertIn(
            "pipeline/extraction/locations/archive_encounter_map.py", gen5_files
        )
        self.assertIn("pipeline/extraction/locations/helpers.py", gen5_files)

    def test_includes_split_trainer_strategy_dependencies(self) -> None:
        class_gender = extraction_source_files(
            "gen4_dppt", "romwiki.pipeline.extraction.trainers.dispatcher"
        )
        battle_mode = extraction_source_files(
            "gen5_bw", "romwiki.pipeline.extraction.trainers.dispatcher"
        )

        self.assertIn("pipeline/extraction/trainers/class_gender.py", class_gender)
        self.assertIn("pipeline/extraction/trainers/battle_mode.py", battle_mode)


if __name__ == "__main__":
    unittest.main()

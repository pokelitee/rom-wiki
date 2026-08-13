from __future__ import annotations

import unittest

from romwiki.pipeline.cache_fingerprint import extraction_source_files


class ExtractionSourceFilesTests(unittest.TestCase):
    def test_scopes_dependencies_to_the_selected_engine(self) -> None:
        files = extraction_source_files("gen4_hgss", "romwiki.pipeline.moves")

        self.assertTrue(any(path.startswith("engines/gen4/hgss/") for path in files))
        self.assertFalse(any(path.startswith("engines/gen4/dppt/") for path in files))
        self.assertFalse(any(path.startswith("engines/gen5/") for path in files))
        self.assertNotIn("engines/registry.py", files)

    def test_includes_overlay_fallback_engine_dependencies(self) -> None:
        files = extraction_source_files("gen5_b2w2", "romwiki.pipeline.items")

        self.assertTrue(any(path.startswith("engines/gen5/b2w2/") for path in files))
        self.assertTrue(any(path.startswith("engines/gen5/bw/") for path in files))

    def test_scopes_dependencies_to_the_selected_extractor(self) -> None:
        files = extraction_source_files("gen4_hgss", "romwiki.pipeline.moves")

        self.assertIn("pipeline/moves.py", files)
        self.assertNotIn("pipeline/locations.py", files)

    def test_includes_split_location_strategy_dependencies(self) -> None:
        files = extraction_source_files("gen4_hgss", "romwiki.pipeline.locations")

        self.assertIn("pipeline/location_arm9_encounter_map.py", files)
        self.assertIn("pipeline/location_helpers.py", files)

        dppt_files = extraction_source_files("gen4_dppt", "romwiki.pipeline.locations")
        self.assertIn("pipeline/location_arm9_event_map.py", dppt_files)
        self.assertIn("pipeline/location_helpers.py", dppt_files)

        gen5_files = extraction_source_files("gen5_bw", "romwiki.pipeline.locations")
        self.assertIn("pipeline/location_archive_encounter_map.py", gen5_files)
        self.assertIn("pipeline/location_helpers.py", gen5_files)


if __name__ == "__main__":
    unittest.main()

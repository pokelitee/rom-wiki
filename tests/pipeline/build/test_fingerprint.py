from __future__ import annotations

import unittest
from pathlib import Path
from typing import Any, cast

from romwiki.engines.registry import _ENGINES
from romwiki.pipeline.build import fingerprint
from romwiki.pipeline.build.fingerprint import (
    GENERATION_EXTRACTOR_MODULES,
    combined_extraction_source_fingerprint,
    extraction_source_files,
)


def _uncached_source_files(
    engine_id: str, extractor_module: str, memo: dict[Any, Any]
) -> tuple[str, ...]:
    """The dependency closure computed without the module-level caches.

    `memo` is scoped to one test so each module is still resolved and parsed
    once there, keeping the comparison fast on slow filesystems.
    """

    def module_path(module_name: str) -> Path | None:
        if module_name not in memo:
            memo[module_name] = fingerprint._module_path.__wrapped__(module_name)
        return cast(Path | None, memo[module_name])

    def local_imports(path: Path, module_name: str) -> frozenset[str]:
        key = (path, module_name)
        if key not in memo:
            memo[key] = fingerprint._local_imports.__wrapped__(path, module_name)
        return cast(frozenset[str], memo[key])

    pending = [extractor_module, *fingerprint._engine_source_modules(engine_id)]
    visited: set[str] = set()
    paths: set[Path] = set()
    while pending:
        module_name = pending.pop()
        if module_name in visited:
            continue
        visited.add(module_name)
        path = module_path(module_name)
        if path is None or module_name == "romwiki.engines.registry":
            continue
        paths.add(path)
        pending.extend(local_imports(path, module_name))
    return tuple(
        sorted(path.relative_to(fingerprint._PACKAGE_ROOT).as_posix() for path in paths)
    )


class ExtractionSourceFilesTests(unittest.TestCase):
    def test_scopes_dependencies_to_the_selected_engine(self) -> None:
        files = extraction_source_files(
            "gen4_hgss", "romwiki.pipeline.extraction.moves"
        )

        self.assertTrue(any(path.startswith("engines/gen4/hgss/") for path in files))
        self.assertFalse(
            any(path.startswith("engines/gen4/platinum/") for path in files)
        )
        self.assertFalse(any(path.startswith("engines/gen5/") for path in files))
        self.assertNotIn("engines/registry.py", files)

    def test_includes_shared_generation_dependencies_but_no_sibling_leaf(
        self,
    ) -> None:
        files = extraction_source_files(
            "gen5_b2w2", "romwiki.pipeline.extraction.items"
        )

        self.assertTrue(any(path.startswith("engines/gen5/b2w2/") for path in files))
        self.assertTrue(any(path.startswith("engines/gen5/shared/") for path in files))
        self.assertFalse(any(path.startswith("engines/gen5/bw/") for path in files))

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
            "gen4_platinum", "romwiki.pipeline.extraction.locations.dispatcher"
        )
        self.assertIn("pipeline/extraction/locations/arm9_event_map.py", dppt_files)
        self.assertIn(
            "pipeline/extraction/locations/arm9_event_map_source.py", dppt_files
        )
        self.assertIn("pipeline/extraction/locations/helpers.py", dppt_files)

        gen5_files = extraction_source_files(
            "gen5_bw", "romwiki.pipeline.extraction.locations.dispatcher"
        )
        for module in (
            "archive_encounter_map",
            "archive_encounter_map_source",
            "archive_location_shops",
        ):
            self.assertIn(f"pipeline/extraction/locations/{module}.py", gen5_files)
        self.assertIn("pipeline/extraction/locations/helpers.py", gen5_files)

    def test_includes_split_encounter_format_dependencies(self) -> None:
        files = extraction_source_files(
            "gen5_b2w2", "romwiki.pipeline.extraction.encounters.dispatcher"
        )

        for strategy in ("conditional", "method_table", "seasonal"):
            self.assertIn(f"pipeline/extraction/encounters/{strategy}.py", files)

    def test_includes_split_trainer_strategy_dependencies(self) -> None:
        class_gender = extraction_source_files(
            "gen4_platinum", "romwiki.pipeline.extraction.trainers.dispatcher"
        )
        battle_mode = extraction_source_files(
            "gen5_bw", "romwiki.pipeline.extraction.trainers.dispatcher"
        )

        self.assertIn("pipeline/extraction/trainers/class_gender.py", class_gender)
        self.assertIn("pipeline/extraction/trainers/battle_mode.py", battle_mode)

    def test_cached_module_parsing_matches_an_uncached_closure(self) -> None:
        # Module parses are shared across every engine and extractor, so a
        # cache keyed too coarsely would leak one closure into another.
        memo: dict[Any, Any] = {}
        for engine_id in sorted(_ENGINES):
            for extractor_module in GENERATION_EXTRACTOR_MODULES:
                with self.subTest(engine=engine_id, extractor=extractor_module):
                    self.assertEqual(
                        extraction_source_files(engine_id, extractor_module),
                        _uncached_source_files(engine_id, extractor_module, memo),
                    )


class CombinedExtractionSourceFingerprintTests(unittest.TestCase):
    def test_is_scoped_to_the_cache_key_and_engine(self) -> None:
        moves = ("romwiki.pipeline.extraction.moves",)
        reference = combined_extraction_source_fingerprint(
            "gen4_hgss", moves, "moves/raw"
        )

        self.assertNotEqual(
            reference,
            combined_extraction_source_fingerprint("gen4_hgss", moves, "items/raw"),
        )
        self.assertNotEqual(
            reference,
            combined_extraction_source_fingerprint("gen4_platinum", moves, "moves/raw"),
        )

    def test_changes_when_an_embedded_datasets_extractor_module_is_added(self) -> None:
        # locations/raw embeds trainer/static-encounter/item/mart/trade
        # datasets as data, not as imports of the location dispatcher's own
        # module -- so the combined fingerprint covering all of them must
        # differ from the location-only fingerprint, or a fix to one of
        # those extractors would silently leave the cached location dataset
        # stale under --incremental.
        location_only = combined_extraction_source_fingerprint(
            "gen4_hgss",
            ("romwiki.pipeline.extraction.locations.dispatcher",),
            "locations/raw",
        )
        with_embedded_datasets = combined_extraction_source_fingerprint(
            "gen4_hgss",
            (
                "romwiki.pipeline.extraction.locations.dispatcher",
                "romwiki.pipeline.extraction.trainers.dispatcher",
                "romwiki.pipeline.extraction.static_encounters",
                "romwiki.pipeline.extraction.items",
                "romwiki.pipeline.extraction.marts",
                "romwiki.pipeline.extraction.trades",
            ),
            "locations/raw",
        )

        self.assertNotEqual(location_only, with_embedded_datasets)

    def test_is_independent_of_module_order(self) -> None:
        forward = combined_extraction_source_fingerprint(
            "gen4_hgss",
            (
                "romwiki.pipeline.extraction.locations.dispatcher",
                "romwiki.pipeline.extraction.trainers.dispatcher",
            ),
            "locations/raw",
        )
        reversed_order = combined_extraction_source_fingerprint(
            "gen4_hgss",
            (
                "romwiki.pipeline.extraction.trainers.dispatcher",
                "romwiki.pipeline.extraction.locations.dispatcher",
            ),
            "locations/raw",
        )

        self.assertEqual(forward, reversed_order)


if __name__ == "__main__":
    unittest.main()

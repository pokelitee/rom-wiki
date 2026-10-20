from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from romwiki.sites.generator_runtime import (
    create_pokedb_archive,
    restore_pokedb_archive,
    write_generator_bundle,
)
from romwiki.sources import PokeDBGeneration
from romwiki.util.errors import SiteError

_ROOT = Path(__file__).resolve().parents[2]


def _write_pokedb(root: Path) -> None:
    for relative, value in {
        "pokemon/default/1.json": {
            "id": 1,
            "name": "bulbasaur",
            "species": "bulbasaur",
        },
        "pokemon/variant/2.json": {
            "id": 2,
            "name": "venusaur-mega",
            "species": "venusaur",
        },
        "ability/1.json": {"id": 1, "name": "stench"},
        "item/1.json": {"id": 1, "name": "master-ball"},
        "move/1.json": {"id": 1, "name": "pound"},
    }.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")


class PokeDBArchiveTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.tmp = Path(directory.name)
        for generation in ("gen3", "gen4"):
            _write_pokedb(self.tmp / "pokedb" / generation)

    def test_round_trips_every_generation_deterministically(self) -> None:
        first = create_pokedb_archive(self.tmp / "pokedb", self.tmp / "a")
        second = create_pokedb_archive(self.tmp / "pokedb", self.tmp / "b")

        self.assertEqual(first.read_bytes(), second.read_bytes())
        self.assertEqual(restore_pokedb_archive(self.tmp / "a", self.tmp / "out"), 2)
        pokedb = PokeDBGeneration.load_pack(
            (self.tmp / "out/gen3.json.gz").read_bytes()
        )
        self.assertEqual(pokedb.move_name(1), "pound")

    def test_rejects_a_tampered_archive(self) -> None:
        archive = create_pokedb_archive(self.tmp / "pokedb", self.tmp / "a")
        archive.write_bytes(archive.read_bytes() + b"\0")

        with self.assertRaisesRegex(SiteError, "checksum mismatch"):
            restore_pokedb_archive(self.tmp / "a", self.tmp / "out")

    def test_requires_a_generation(self) -> None:
        with self.assertRaisesRegex(SiteError, "No PokéDB generations"):
            create_pokedb_archive(self.tmp / "missing", self.tmp / "a")


class GeneratorBundleTests(unittest.TestCase):
    def test_lays_out_checksummed_downloads_with_the_repository_resources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            _write_pokedb(tmp / "pokedb/gen4")
            create_pokedb_archive(tmp / "pokedb", tmp / "pin")
            restore_pokedb_archive(tmp / "pin", tmp / "packs")
            wheel = tmp / "romwiki-0.1.0-py3-none-any.whl"
            wheel.write_bytes(b"wheel")

            manifest = write_generator_bundle(_ROOT, wheel, tmp / "packs", tmp / "out")

            output = tmp / "out"
            self.assertEqual(
                json.loads((output / "manifest.json").read_text("utf-8")), manifest
            )
            wheel_entry = manifest["wheel"]
            assert isinstance(wheel_entry, dict)
            self.assertTrue(wheel_entry["path"].endswith("/" + wheel.name))
            self.assertEqual((output / wheel_entry["path"]).read_bytes(), b"wheel")
            resources = manifest["resources"]
            assert isinstance(resources, dict)
            with zipfile.ZipFile(output / resources["path"]) as archive:
                names = set(archive.namelist())
            self.assertIn("profiles/symbols/firered-us.toml", names)
            self.assertIn("sites/portal/site.toml", names)
            self.assertIn("sites/games/emerald/game.toml", names)
            self.assertFalse(any("/wiki/data/" in name for name in names))
            pokedb = manifest["pokedb"]
            assert isinstance(pokedb, dict)
            self.assertEqual(list(pokedb), ["4"])

    def test_will_not_replace_an_unrelated_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            (tmp / "out").mkdir()
            (tmp / "out/keep.txt").write_text("mine", encoding="utf-8")

            with self.assertRaisesRegex(SiteError, "not an earlier bundle"):
                write_generator_bundle(_ROOT, tmp / "x.whl", tmp, tmp / "out")
            self.assertTrue((tmp / "out/keep.txt").is_file())


if __name__ == "__main__":
    unittest.main()

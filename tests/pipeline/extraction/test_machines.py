from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from romwiki.engines.gen5.bw import MACHINE_TABLE_LOCATOR
from romwiki.pipeline.extraction.machines import extract_machine_dataset
from romwiki.profiles.models import GameProfile
from romwiki.schema.versions import MACHINES_RAW_SCHEMA_VERSION
from romwiki.util.errors import InvalidRomError, ProfileError


def _profile(**overrides: object) -> GameProfile:
    fields: dict[str, Any] = {
        "id": "test",
        "name": "Test",
        "platform": "nintendo-ds",
        "engine": "gen4_platinum",
        "base_game": "platinum",
        "game_codes": ("CPUE",),
        "rom_versions": (1,),
        "hashes": (),
        "layout": {},
        "parameters": {},
    }
    fields.update(overrides)
    return GameProfile(**fields)


def _move_table(count: int, move_id: int = 1) -> bytes:
    return (move_id.to_bytes(2, "little")) * count


class OffsetFormatMachineExtractionTests(unittest.TestCase):
    """Covers gen4_platinum's `profile-offset` branch with real binary parsing."""

    def _write_rom(self, tmp_path, prefix: bytes, table: bytes, suffix: bytes = b""):
        rom_path = tmp_path / "rom.bin"
        data = prefix + table + suffix
        rom_path.write_bytes(data)
        return rom_path, len(data)

    def test_reads_and_parses_the_machine_table_from_a_fixed_offset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            table = _move_table(100)
            path, size = self._write_rom(Path(tmp), b"\x00" * 16, table)
            profile = _profile(parameters={"machine_move_offset": 16})
            result = SimpleNamespace(
                match=SimpleNamespace(profile=profile),
                image=SimpleNamespace(
                    path=path, size=size, hashes=SimpleNamespace(sha256="deadbeef")
                ),
            )

            dataset = extract_machine_dataset(result)

        self.assertEqual(dataset["schema_version"], MACHINES_RAW_SCHEMA_VERSION)
        self.assertEqual(dataset["dataset"], "machines")
        self.assertEqual(dataset["record_count"], 100)
        self.assertEqual(
            dataset["source"],
            {"rom_sha256": "deadbeef", "offset": 16, "size": 200},
        )
        self.assertEqual(
            dataset["records"][0],
            {
                "machine_id": 1,
                "kind": "tm",
                "number": 1,
                "move_id": 1,
                "table_index": 0,
                "item_id": 328,
                "name": "TM01",
            },
        )
        self.assertEqual(
            dataset["records"][92],
            {
                "machine_id": 93,
                "kind": "hm",
                "number": 1,
                "move_id": 1,
                "table_index": 92,
                "item_id": 420,
                "name": "HM01",
            },
        )

    def test_honors_machine_count_and_tm_count_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            table = _move_table(10)
            path, size = self._write_rom(Path(tmp), b"", table)
            profile = _profile(
                parameters={
                    "machine_move_offset": 0,
                    "machine_count": 10,
                    "tm_count": 5,
                }
            )
            result = SimpleNamespace(
                match=SimpleNamespace(profile=profile),
                image=SimpleNamespace(
                    path=path, size=size, hashes=SimpleNamespace(sha256="abc")
                ),
            )

            dataset = extract_machine_dataset(result)

        self.assertEqual(dataset["record_count"], 10)
        self.assertEqual(dataset["records"][5]["kind"], "hm")
        self.assertEqual(dataset["records"][5]["number"], 1)

    def test_raises_when_offset_parameter_is_missing(self) -> None:
        profile = _profile(parameters={})
        result = SimpleNamespace(
            match=SimpleNamespace(profile=profile),
            image=SimpleNamespace(size=1000, hashes=SimpleNamespace(sha256="x")),
        )
        with self.assertRaisesRegex(ProfileError, "does not define a machine"):
            extract_machine_dataset(result)

    def test_raises_when_offset_is_out_of_bounds(self) -> None:
        profile = _profile(parameters={"machine_move_offset": 1000})
        result = SimpleNamespace(
            match=SimpleNamespace(profile=profile),
            image=SimpleNamespace(size=1000, hashes=SimpleNamespace(sha256="x")),
        )
        with self.assertRaisesRegex(InvalidRomError, "outside the ROM image"):
            extract_machine_dataset(result)


class Arm9PrefixMachineExtractionTests(unittest.TestCase):
    """Covers gen4_hgss/gen5_bw's `binary-prefix` branch."""

    def _profile(self, **parameters: object) -> GameProfile:
        return _profile(engine="gen5_bw", parameters=parameters)

    def test_locates_and_parses_the_machine_table_using_the_default_locator(
        self,
    ) -> None:
        prefix = bytes.fromhex(MACHINE_TABLE_LOCATOR)
        table = _move_table(101)
        arm9 = b"padding-before-the-table" + prefix + table + b"trailing"
        profile = self._profile()
        platform = SimpleNamespace(read_decompressed_code_binary=lambda image: arm9)
        result = SimpleNamespace(
            match=SimpleNamespace(profile=profile),
            image=SimpleNamespace(hashes=SimpleNamespace(sha256="cafe")),
        )

        with patch(
            "romwiki.pipeline.extraction.machines.get_platform", return_value=platform
        ):
            dataset = extract_machine_dataset(result)

        expected_offset = len(b"padding-before-the-table") + len(prefix)
        self.assertEqual(dataset["record_count"], 101)
        self.assertEqual(dataset["source"]["arm9_prefix"], MACHINE_TABLE_LOCATOR)
        self.assertEqual(dataset["source"]["arm9_offset"], expected_offset)
        self.assertEqual(dataset["source"]["size"], 202)
        self.assertEqual(dataset["records"][0]["item_id"], 328)

    def test_honors_a_custom_machine_move_prefix_parameter(self) -> None:
        custom_prefix_hex = "aabbccdd"
        prefix = bytes.fromhex(custom_prefix_hex)
        table = _move_table(101)
        arm9 = b"pad" + prefix + table
        profile = self._profile(machine_move_prefix=custom_prefix_hex)
        platform = SimpleNamespace(read_decompressed_code_binary=lambda image: arm9)
        result = SimpleNamespace(
            match=SimpleNamespace(profile=profile),
            image=SimpleNamespace(hashes=SimpleNamespace(sha256="cafe")),
        )

        with patch(
            "romwiki.pipeline.extraction.machines.get_platform", return_value=platform
        ):
            dataset = extract_machine_dataset(result)

        self.assertEqual(dataset["source"]["arm9_prefix"], custom_prefix_hex)

    def test_raises_when_the_locator_pattern_is_not_found(self) -> None:
        arm9 = b"no locator pattern here"
        profile = self._profile()
        platform = SimpleNamespace(read_decompressed_code_binary=lambda image: arm9)
        result = SimpleNamespace(
            match=SimpleNamespace(profile=profile),
            image=SimpleNamespace(hashes=SimpleNamespace(sha256="cafe")),
        )

        with (
            patch(
                "romwiki.pipeline.extraction.machines.get_platform",
                return_value=platform,
            ),
            self.assertRaisesRegex(InvalidRomError, "Could not locate"),
        ):
            extract_machine_dataset(result)

    def test_raises_when_the_locator_pattern_is_not_unique(self) -> None:
        prefix = bytes.fromhex(MACHINE_TABLE_LOCATOR)
        table = _move_table(101)
        arm9 = prefix + table + prefix + table
        profile = self._profile()
        platform = SimpleNamespace(read_decompressed_code_binary=lambda image: arm9)
        result = SimpleNamespace(
            match=SimpleNamespace(profile=profile),
            image=SimpleNamespace(hashes=SimpleNamespace(sha256="cafe")),
        )

        with (
            patch(
                "romwiki.pipeline.extraction.machines.get_platform",
                return_value=platform,
            ),
            self.assertRaisesRegex(InvalidRomError, "not unique"),
        ):
            extract_machine_dataset(result)

    def test_raises_when_the_table_extends_past_the_decompressed_arm9(self) -> None:
        prefix = bytes.fromhex(MACHINE_TABLE_LOCATOR)
        arm9 = b"pad" + prefix + _move_table(5)
        profile = self._profile()
        platform = SimpleNamespace(read_decompressed_code_binary=lambda image: arm9)
        result = SimpleNamespace(
            match=SimpleNamespace(profile=profile),
            image=SimpleNamespace(hashes=SimpleNamespace(sha256="cafe")),
        )

        with (
            patch(
                "romwiki.pipeline.extraction.machines.get_platform",
                return_value=platform,
            ),
            self.assertRaisesRegex(InvalidRomError, "outside the decompressed ARM9"),
        ):
            extract_machine_dataset(result)


class MachineExtractionDispatchTests(unittest.TestCase):
    def test_requires_a_known_profile(self) -> None:
        result = SimpleNamespace(match=None, image=SimpleNamespace())
        with self.assertRaises(ProfileError):
            extract_machine_dataset(result)

    def test_raises_for_an_unsupported_machine_format(self) -> None:
        profile = _profile(engine="gen4_platinum")
        result = SimpleNamespace(
            match=SimpleNamespace(profile=profile), image=SimpleNamespace()
        )
        fake_adapter = SimpleNamespace(formats=SimpleNamespace(machines="none"))

        with (
            patch(
                "romwiki.pipeline.extraction.machines.get_engine",
                return_value=fake_adapter,
            ),
            self.assertRaisesRegex(ProfileError, "does not support machine"),
        ):
            extract_machine_dataset(result)


if __name__ == "__main__":
    unittest.main()

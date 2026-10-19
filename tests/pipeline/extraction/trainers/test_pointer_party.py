from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.pipeline.extraction.trainers.pointer_party import (
    extract_pointer_party_trainer_dataset,
)
from romwiki.profiles.models import GameProfile, HashMatch, KnownHash
from romwiki.util.errors import InvalidRomError

_CLASS_NAMES = 0x00
_TRAINERS = 0x40


def _rom(*class_ids: int) -> bytes:
    """Two 13-byte class names ("LASS", "PKMN TRAINER"), then one empty-party
    trainer per class ID, each named "AMY"."""
    rom = bytearray(_TRAINERS + 0x28 * len(class_ids))
    rom[0:5] = bytes([0xC6, 0xBB, 0xCD, 0xCD, 0xFF])
    rom[13:24] = bytes(
        [0x53, 0x54, 0x00, 0xCE, 0xCC, 0xBB, 0xC3, 0xC8, 0xBF, 0xCC, 0xFF]
    )
    for index, class_id in enumerate(class_ids):
        record = _TRAINERS + 0x28 * index
        rom[record + 1] = class_id
        rom[record + 4 : record + 8] = bytes([0xBB, 0xC7, 0xD3, 0xFF])
    return bytes(rom)


def _extract(rom: bytes, **parameters: int) -> dict:
    profile = GameProfile(
        id="test-frlg",
        name="Test",
        platform="game-boy-advance",
        engine="gen3_frlg",
        base_game="firered",
        game_codes=(),
        rom_versions=(),
        hashes=(KnownHash(algorithm="sha256", value="abc", variant="retail"),),
        layout={},
        parameters={"trainer_offset": _TRAINERS, **parameters},
    )
    image = Mock()
    image.hashes.sha256 = "abc"
    result = InspectionResult(
        image=image, match=HashMatch(profile=profile, known_hash=profile.hashes[0])
    )
    platform = SimpleNamespace(
        read_bytes=lambda image, offset, size: rom[offset : offset + size]
    )
    with patch(
        "romwiki.pipeline.extraction.trainers.pointer_party.get_platform",
        return_value=platform,
    ):
        return extract_pointer_party_trainer_dataset(result)


class PointerPartyClassNameTests(unittest.TestCase):
    def test_names_each_trainers_class_from_the_class_table(self) -> None:
        dataset = _extract(
            _rom(1, 0),
            trainer_count=2,
            trainer_class_name_offset=_CLASS_NAMES,
            trainer_class_count=2,
        )

        self.assertEqual(
            [(record["class_name"], record["name"]) for record in dataset["records"]],
            [("PKMN Trainer", "Amy"), ("Lass", "Amy")],
        )

    def test_leaves_class_names_undecoded_without_a_class_table(self) -> None:
        dataset = _extract(_rom(1), trainer_count=1)

        self.assertIsNone(dataset["records"][0]["class_name"])

    def test_rejects_a_class_beyond_the_class_table(self) -> None:
        with self.assertRaisesRegex(InvalidRomError, "has class 2"):
            _extract(
                _rom(2),
                trainer_count=1,
                trainer_class_name_offset=_CLASS_NAMES,
                trainer_class_count=2,
            )


if __name__ == "__main__":
    unittest.main()

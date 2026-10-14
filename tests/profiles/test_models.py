from __future__ import annotations

import unittest
from typing import Any

from romwiki.profiles.models import GameProfile
from romwiki.util.errors import ProfileError


def _profile(**parameters: Any) -> GameProfile:
    return GameProfile(
        id="test",
        name="Test",
        platform="nintendo-ds",
        engine="gen5_bw",
        base_game="black",
        game_codes=("IRBO",),
        rom_versions=(0,),
        hashes=(),
        parameters=parameters,
    )


class IntParameterTests(unittest.TestCase):
    def test_returns_a_declared_integer(self) -> None:
        self.assertEqual(_profile(tm_count=92).int_parameter("tm_count"), 92)

    def test_prefers_a_declared_zero_over_the_default(self) -> None:
        self.assertEqual(_profile(tm_count=0).int_parameter("tm_count", 92), 0)

    def test_falls_back_to_the_default_when_omitted(self) -> None:
        self.assertEqual(_profile().int_parameter("tm_count", 92), 92)

    def test_rejects_a_missing_parameter_without_a_default(self) -> None:
        with self.assertRaisesRegex(ProfileError, "missing parameter 'tm_count'"):
            _profile().int_parameter("tm_count")

    def test_rejects_a_non_integer_value(self) -> None:
        with self.assertRaisesRegex(ProfileError, "'tm_count' must be an integer"):
            _profile(tm_count="92").int_parameter("tm_count")

    def test_rejects_a_boolean_value(self) -> None:
        with self.assertRaisesRegex(ProfileError, "must be an integer, not bool"):
            _profile(tm_count=True).int_parameter("tm_count")


class OptionalIntParameterTests(unittest.TestCase):
    def test_returns_none_when_omitted(self) -> None:
        self.assertIsNone(_profile().optional_int_parameter("tm_count"))

    def test_rejects_a_non_integer_value(self) -> None:
        with self.assertRaises(ProfileError):
            _profile(tm_count=1.5).optional_int_parameter("tm_count")


if __name__ == "__main__":
    unittest.main()

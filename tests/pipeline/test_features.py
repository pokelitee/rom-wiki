from __future__ import annotations

import unittest
from pathlib import Path

from romwiki.pipeline.features import effective_features
from romwiki.profiles.loader import ProfileRepository


class DatasetFeatureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.profiles = {
            profile.id: profile
            for profile in ProfileRepository.load(Path("profiles")).profiles
        }

    def test_generation_capabilities_are_profile_aware(self) -> None:
        platinum = set(effective_features(self.profiles["platinum-us"]))
        black = set(effective_features(self.profiles["black-us"]))

        self.assertIn("contests", platinum)
        self.assertIn("move-tutors", platinum)
        self.assertNotIn("post-battle-healing", platinum)
        self.assertIn("post-battle-healing", black)
        self.assertIn("victory-items", black)
        self.assertNotIn("move-tutors", black)


if __name__ == "__main__":
    unittest.main()

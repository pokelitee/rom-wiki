from __future__ import annotations

import unittest

from romwiki.pipeline.location_sections import (
    location_reference_label,
    resolve_location_section,
    validate_location_sections,
)
from romwiki.profiles.models import GameProfile, KnownHash, LocationSectionConfig
from romwiki.util.errors import ProfileError


class LocationSectionResolverTests(unittest.TestCase):
    def test_prefers_profile_labels_and_falls_back_to_native_names(self) -> None:
        profile = GameProfile(
            id="example-hack",
            name="Example Hack",
            platform="nintendo-ds",
            engine="gen4_hgss",
            base_game="heartgold",
            game_codes=("TEST",),
            rom_versions=(0,),
            hashes=(KnownHash("sha256", "00", "test"),),
            location_sections=LocationSectionConfig(
                by_header={7: "Header-specific room"},
                by_internal_name={"MAP_CUSTOM": "Custom 2F"},
            ),
        )

        self.assertEqual(
            resolve_location_section(profile, header_id=9, internal_name="MAP_CUSTOM"),
            (
                "Custom 2F",
                {
                    "source": "profile",
                    "profile": "example-hack",
                    "key": "MAP_CUSTOM",
                },
            ),
        )
        self.assertEqual(
            resolve_location_section(profile, header_id=7, internal_name="MAP_CUSTOM")[
                0
            ],
            "Header-specific room",
        )
        self.assertEqual(
            resolve_location_section(profile, header_id=10, internal_name="D25R0102"),
            (
                "D25R0102",
                {"source": "rom", "field": "internal_name"},
            ),
        )
        self.assertEqual(
            resolve_location_section(profile, header_id=11, internal_name=None),
            (None, None),
        )

    def test_combines_rom_section_with_display_name_for_references(self) -> None:
        self.assertEqual(
            location_reference_label(
                {
                    "name": "Canalave City",
                    "section_name": "C02PC0101",
                    "section_name_source": {
                        "source": "rom",
                        "field": "internal_name",
                    },
                }
            ),
            "Canalave City — C02PC0101",
        )

    def test_rejects_unmatched_and_conflicting_selectors(self) -> None:
        unmatched = _profile(
            LocationSectionConfig(
                by_header={99: "Missing room"},
                by_internal_name={"MISSING": "Missing room"},
            )
        )
        with self.assertRaisesRegex(
            ProfileError, "header-099.*internal name 'MISSING'"
        ):
            validate_location_sections(unmatched, [(1, "MAP_ONE")])

        conflicting = _profile(
            LocationSectionConfig(
                by_header={1: "Example Cave 1F"},
                by_internal_name={"MAP_ONE": "Example Cave B1F"},
            )
        )
        with self.assertRaisesRegex(ProfileError, "conflicting.*header-001"):
            validate_location_sections(conflicting, [(1, "MAP_ONE")])


def _profile(location_sections: LocationSectionConfig) -> GameProfile:
    return GameProfile(
        id="example-hack",
        name="Example Hack",
        platform="nintendo-ds",
        engine="gen4_hgss",
        base_game="heartgold",
        game_codes=("TEST",),
        rom_versions=(0,),
        hashes=(KnownHash("sha256", "00", "test"),),
        location_sections=location_sections,
    )


if __name__ == "__main__":
    unittest.main()

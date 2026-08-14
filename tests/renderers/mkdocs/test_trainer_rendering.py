from __future__ import annotations

import unittest

from romwiki.renderers.mkdocs.trainers import (
    _append_ai_battle_items,
    _append_party,
    _append_same_name_trainers,
    _group_ai_battle_items,
    _party_cards,
    _party_gender,
    _trainer_location_coverage_notice,
    _trainer_provenance,
    _trainer_summary,
    _trainer_variant_coverage_notice,
    _variant_tab_label,
)


class TrainerRenderingTests(unittest.TestCase):
    def test_summarizes_unlinked_active_trainer_records(self) -> None:
        notice = _trainer_location_coverage_notice(
            [
                {"party": [{}], "locations": [], "script_references": []},
                {"party": [{}], "locations": [{}], "script_references": []},
                {"party": [], "locations": [], "script_references": []},
            ]
        )

        self.assertIn("1 active trainer record", notice)
        self.assertIn("facilities, dynamic dispatch, and unused records", notice)

    def test_warns_when_trainer_variant_grouping_is_incomplete(self) -> None:
        notice = _trainer_variant_coverage_notice(
            {
                "starter_choice": {"status": "verified", "note": "Complete."},
                "story_stage": {
                    "status": "unresolved",
                    "note": "The selector has not been decoded.",
                },
            }
        )

        self.assertIn("Trainer variant coverage is not exhaustive", notice)
        self.assertIn("Story Stage (unresolved)", notice)
        self.assertIn("selector has not been decoded", notice)
        self.assertNotIn("Starter Choice", notice)

    def test_uses_only_named_public_axes_and_generic_fallback(self) -> None:
        self.assertEqual(
            _variant_tab_label(
                {
                    "conditions": [
                        {"kind": "season", "value": "winter"},
                        {"kind": "rematch-stage", "value": "rematch"},
                        {"kind": "sibling-version", "value": "white-2"},
                    ]
                },
                1,
            ),
            "Winter · Rematch · White 2",
        )
        self.assertEqual(
            _variant_tab_label(
                {"conditions": [{"kind": "story-stage", "value": "late-game"}]},
                3,
            ),
            "Variant 3",
        )

    def test_renders_verified_battle_variants_as_complete_party_tabs(self) -> None:
        current = _related_trainer(161, "Aspertia City", 5, "Tepig")
        related = _related_trainer(162, "Aspertia City", 5, "Oshawott")
        family = {
            "id": "hugh-aspertia",
            "label": "Aspertia City rival battle",
            "order": 0,
            "provenance": {
                "source": "ROM field-script selection",
                "reference": "script:12@0x40",
                "verification": "All dispatch targets were checked.",
            },
            "variants": [
                {
                    "trainer_id": 161,
                    "order": 0,
                    "conditions": [
                        {
                            "kind": "starter-choice",
                            "value": "snivy",
                            "label": "Player chose Snivy",
                        }
                    ],
                },
                {
                    "trainer_id": 162,
                    "order": 1,
                    "conditions": [
                        {
                            "kind": "starter-choice",
                            "value": "tepig",
                            "label": "Player chose Tepig",
                        }
                    ],
                },
            ],
        }
        lines: list[str] = []

        _append_party(
            lines,
            current,
            [(family, family["variants"][0])],
            {161: current, 162: related},
            "trainers/trainer-0161.md",
            "trainers/trainer-0161/",
        )
        page = "\n".join(lines)

        self.assertIn("## Party", page)
        self.assertIn('=== "Snivy"', page)
        self.assertIn('=== "Tepig"', page)
        self.assertIn("Exact record: [trainer-0161]", page)
        self.assertIn("Exact record: [trainer-0162]", page)
        self.assertNotIn("Battle Variants", page)
        self.assertIn("Tepig", page)
        self.assertIn("Oshawott", page)

    def test_links_selections_without_tabs_when_all_parties_are_identical(self) -> None:
        current = _related_trainer(161, "Aspertia City", 5, "Tepig")
        related = _related_trainer(162, "Aspertia City", 5, "Tepig")
        family = {
            "id": "hugh-aspertia",
            "label": "Aspertia City rival battle",
            "order": 0,
            "variants": [
                {
                    "trainer_id": trainer_id,
                    "order": order,
                    "conditions": [
                        {"kind": "starter-choice", "value": starter, "label": starter}
                    ],
                }
                for order, (trainer_id, starter) in enumerate(
                    ((161, "snivy"), (162, "tepig"))
                )
            ],
        }
        lines: list[str] = []

        _append_party(
            lines,
            current,
            [(family, family["variants"][0])],
            {161: current, 162: related},
            "trainers/trainer-0161.md",
            "trainers/trainer-0161/",
        )
        page = "\n".join(lines)

        self.assertNotIn('=== "', page)
        self.assertIn("Selections: [Snivy (trainer-0161)]", page)
        self.assertIn("[Tepig (trainer-0162)]", page)
        self.assertEqual(page.count('class="rw-party-grid"'), 1)

    def test_consolidates_location_methods_in_data_provenance(self) -> None:
        lines = _trainer_provenance(
            {
                "class_id": 1,
                "class_gender": "female",
                "ai_flags": 0,
                "battle_type": 0,
                "unknown_byte": 0x30,
                "base_prize_money": {
                    "amount": 4320,
                    "final_party_level": 27,
                    "multiplier": 40,
                    "base_factor": 4,
                    "battle_format_multiplier": 1,
                    "multiplier_provenance": {
                        "source": "rom",
                        "overlay_id": 16,
                        "offset": 0x35A00,
                        "class_id": 32,
                    },
                },
                "provenance": {"archive": "trdata.narc", "member": 5},
                "party_provenance": {"archive": "trpoke.narc", "member": 5},
                "locations": [{"name": "Route 202"}],
                "script_references": [{"name": "Route 203"}],
            }
        )
        provenance = "\n".join(lines)

        self.assertIn("Source: exact ROM trainer record from", provenance)
        self.assertIn("Overworld locations:", provenance)
        self.assertIn("Scripted battle locations:", provenance)
        self.assertIn("`StartTrainerBattle`", provenance)
        self.assertIn("| Unknown byte | `0x30` |", provenance)
        self.assertIn("| Class gender | Female |", provenance)
        self.assertIn("ARM9 overlay `16` at byte offset `0x35A00`", provenance)

    def test_renders_same_name_trainers_without_assuming_identity(self) -> None:
        current = _related_trainer(5, "Route 202", 8, "Starly")
        related = _related_trainer(19, "Route 204", 12, "Staravia")
        related["party"].extend(
            [
                {
                    "level": 12,
                    "pokemon": {"id": pokemon_id, "name": name, "slug": slug},
                }
                for pokemon_id, name, slug in (
                    (74, "Geodude", "geodude"),
                    (41, "Zubat", "zubat"),
                    (66, "Machop", "machop"),
                )
            ]
        )
        lines: list[str] = []

        _append_same_name_trainers(
            lines,
            current,
            [current, related],
            "trainers/trainer-0005.md",
        )
        page = "\n".join(lines)

        self.assertIn("## Same-name trainers", page)
        self.assertNotIn("<details", page)
        self.assertIn("does not establish that they represent the same character", page)
        self.assertIn("`trainer-0019`", page)
        self.assertIn("Route 204", page)
        self.assertIn("[Staravia](../pokemon/staravia.md)", page)
        self.assertIn("[Machop](../pokemon/machop.md)", page)
        self.assertNotIn("more", page)

    def test_renders_difficulty_parties_without_mechanics_prose(self) -> None:
        normal = _related_trainer(156, "Aspertia City", 13, "Lillipup")
        challenge = _related_trainer(764, "Aspertia City", 14, "Lillipup")
        family = {
            "id": "gym-cheren",
            "label": "Cheren Gym battle",
            "order": 0,
            "provenance": {
                "source": "ROM script",
                "reference": "gym:cheren",
                "verification": "Dispatch targets verified.",
            },
            "variants": [
                {
                    "trainer_id": trainer_id,
                    "order": order,
                    "conditions": [
                        {
                            "kind": "difficulty-mode",
                            "value": mode,
                            "label": f"{mode.title()} mode",
                        }
                    ],
                }
                for order, (mode, trainer_id) in enumerate(
                    (("easy", 156), ("normal", 156), ("challenge", 764))
                )
            ],
        }
        lines: list[str] = []

        _append_party(
            lines,
            normal,
            [(family, family["variants"][0])],
            {156: normal, 764: challenge},
            "trainers/trainer-0156.md",
            "trainers/trainer-0156/",
        )
        page = "\n".join(lines)

        self.assertIn('=== "Easy"', page)
        self.assertIn('=== "Normal"', page)
        self.assertIn('=== "Challenge"', page)
        self.assertNotIn("Difficulty behavior", page)
        self.assertNotIn("displayed level", page)

    def test_collapses_large_same_name_groups(self) -> None:
        current = _related_trainer(1, "Route 201", 5, "Bidoof")
        related = [
            _related_trainer(trainer_id, "Galactic HQ", 20, "Zubat")
            for trainer_id in range(2, 8)
        ]
        lines: list[str] = []

        _append_same_name_trainers(
            lines,
            current,
            [current, *related],
            "trainers/trainer-0001.md",
        )
        page = "\n".join(lines)

        self.assertIn('<details markdown="1">', page)
        self.assertIn("<summary>6 other parties</summary>", page)

    def test_groups_ai_battle_item_slots_and_renders_icons(self) -> None:
        record = {
            "ai_battle_items": [
                {
                    "id": 23,
                    "name": "Full Restore",
                    "slug": "full-restore",
                    "sprite_url": "https://example.test/full-restore.png",
                },
                {
                    "id": 23,
                    "name": "Full Restore",
                    "slug": "full-restore",
                    "sprite_url": "https://example.test/full-restore.png",
                },
            ]
        }
        lines: list[str] = []

        _append_ai_battle_items(
            lines, _group_ai_battle_items(record), "trainers/trainer-0005.md"
        )
        page = "\n".join(lines)

        self.assertEqual(page.count("[Full Restore](../items/full-restore.md)"), 1)
        self.assertIn('src="https://example.test/full-restore.png"', page)
        self.assertIn("| 2 |", page)

    def test_omits_empty_ai_battle_item_section(self) -> None:
        lines: list[str] = []

        _append_ai_battle_items(lines, [], "trainers/test.md")

        self.assertEqual(lines, [])

    def test_summarizes_grouped_ai_battle_items(self) -> None:
        record = {
            "trainer_id": 5,
            "class_name": "leader",
            "locations": [],
            "script_references": [],
            "double_battle": False,
            "party": [_party_member([])],
            "ai_battle_items": [
                {"id": 23, "name": "Full Restore", "slug": "full-restore"},
                {"id": 23, "name": "Full Restore", "slug": "full-restore"},
            ],
        }

        page = "\n".join(
            _trainer_summary(
                record,
                _group_ai_battle_items(record),
                "trainers/trainer-0005/",
            )
        )

        self.assertIn(
            '<dt>AI items</dt><dd><a href="../../items/full-restore/">'
            "Full Restore</a> ×2</dd>",
            page,
        )

    def test_summarizes_gen5_post_battle_rewards(self) -> None:
        record = {
            "trainer_id": 5,
            "class_name": "leader",
            "locations": [],
            "script_references": [],
            "double_battle": False,
            "party": [_party_member([])],
            "ai_battle_items": [],
            "healer": True,
            "victory_item": {
                "id": 23,
                "name": "Full Restore",
                "slug": "full-restore",
            },
        }

        page = "\n".join(_trainer_summary(record, [], "trainers/trainer-0005/"))

        self.assertIn("Heals the player's party", page)
        self.assertIn("<dt>Victory item</dt>", page)
        self.assertIn("../../items/full-restore/", page)

    def test_omits_unsupported_gen5_summary_fields(self) -> None:
        record = {
            "trainer_id": 5,
            "class_name": "leader",
            "locations": [],
            "script_references": [],
            "double_battle": False,
            "party": [_party_member([])],
            "ai_battle_items": [],
            "healer": True,
            "victory_item": {
                "id": 23,
                "name": "Full Restore",
                "slug": "full-restore",
            },
        }

        page = "\n".join(
            _trainer_summary(
                record,
                [],
                "trainers/trainer-0005/",
                features=frozenset(),
            )
        )

        self.assertNotIn("<dt>After victory</dt>", page)
        self.assertNotIn("<dt>Victory item</dt>", page)

    def test_summarizes_exact_base_prize_money(self) -> None:
        record = {
            "trainer_id": 5,
            "class_name": "leader",
            "locations": [],
            "script_references": [],
            "double_battle": False,
            "party": [_party_member([])],
            "ai_battle_items": [],
            "base_prize_money": {
                "amount": 2400,
                "final_party_level": 20,
                "multiplier": 30,
                "base_factor": 4,
                "battle_format_multiplier": 1,
            },
        }

        page = "\n".join(_trainer_summary(record, [], "trainers/trainer-0005/"))

        self.assertIn("<dt>Base prize money</dt><dd>&#8381;2,400</dd>", page)

    def test_numbers_explicit_moves_in_rom_order(self) -> None:
        party = [_party_member(["tackle", "growl"])]

        page = "\n".join(_party_cards(party, "trainers/trainer-0001/"))

        self.assertIn('<ol class="rw-party-card__moves"', page)
        self.assertIn('aria-label="Bulbasaur moves"', page)
        self.assertLess(page.index("Tackle"), page.index("Growl"))
        self.assertIn('<span class="rw-party-card__move-name">', page)
        self.assertNotIn("default level-up moves", page)

    def test_formats_gender_symbols_with_accessible_labels(self) -> None:
        self.assertIn('aria-label="Male"', _party_gender({"name": "Male"}))
        self.assertIn("♂", _party_gender({"name": "Male"}))
        self.assertIn('aria-label="Female"', _party_gender({"name": "Female"}))
        self.assertIn("♀", _party_gender({"name": "Female"}))
        self.assertIn('aria-label="Genderless"', _party_gender({"name": "Genderless"}))
        self.assertIn("⚲", _party_gender({"name": "Genderless"}))
        unknown = _party_gender({"name": 'Future & "variant"'})
        self.assertIn('aria-label="Future &amp; &quot;variant&quot;"', unknown)
        self.assertIn("rw-party-card__gender--unknown", unknown)

    def test_omits_optional_fields_missing_from_another_engine(self) -> None:
        member = _party_member([])
        for key in ("ability", "nature", "gender", "ivs", "evs", "calculated_stats"):
            member.pop(key)

        page = "\n".join(_party_cards([member], "trainers/trainer-0001/"))

        self.assertIn("Bulbasaur", page)
        self.assertNotIn("<dt>Nature</dt>", page)
        self.assertNotIn("<dt>Ability</dt>", page)
        self.assertNotIn('<h4 class="rw-party-card__section-title">Stats</h4>', page)

    def test_formats_default_moves_without_a_numbered_slot(self) -> None:
        page = "\n".join(_party_cards([_party_member([])], "trainers/trainer-0001/"))

        self.assertNotIn('<ol class="rw-party-card__moves"', page)
        self.assertIn("Uses default level-up moves.", page)

    def test_labels_derived_default_moves(self) -> None:
        member = _party_member(["Tackle", "Growl"])
        member["moves_source"] = "level-up"

        page = "\n".join(_party_cards([member], "trainers/trainer-0001/"))

        self.assertIn("Tackle", page)
        self.assertIn("Growl", page)
        self.assertIn(
            "Derived from the Pokémon's level-up learnset at this level.", page
        )

    def test_renders_available_party_attributes_compactly(self) -> None:
        member = _party_member([])
        member.update(
            {
                "ability": {
                    "id": 65,
                    "name": "Overgrow",
                    "slug": "overgrow",
                    "slot": 1,
                    "source": "derived",
                },
                "ivs": {"source": "derived", "values": _stats(12)},
                "evs": {"source": "engine-default", "values": _stats(0)},
                "calculated_stats": {"source": "derived", "values": _stats(42)},
            }
        )

        page = "\n".join(_party_cards([member], "trainers/trainer-0001/"))

        self.assertIn('href="../../abilities/overgrow/">Overgrow</a>', page)
        self.assertIn('<span class="rw-party-card__level">Lv. 5</span>', page)
        self.assertIn(
            '<dl class="rw-party-card__details rw-party-card__section">', page
        )
        self.assertIn('<h4 class="rw-party-card__section-title">Stats</h4>', page)
        self.assertIn('<h4 class="rw-party-card__section-title">Moves</h4>', page)
        self.assertIn('<table class="rw-party-card__stats">', page)
        self.assertIn('<tr><th scope="row">Value</th><td>42</td>', page)
        self.assertIn('<tr><th scope="row">IV</th><td>12</td>', page)
        self.assertIn('<tr><th scope="row">EV</th><td>0</td>', page)

    def test_renders_minimum_and_maximum_rows_when_any_stat_is_ranged(self) -> None:
        member = _party_member([])
        values = _stats(42)
        values["attack"] = {"minimum": 38, "maximum": 45}
        member["calculated_stats"] = {"source": "derived", "values": values}
        member["ivs"] = {"source": "derived", "values": _stats(12)}
        member["evs"] = {"source": "engine-default", "values": _stats(0)}

        page = "\n".join(_party_cards([member], "trainers/trainer-0001/"))

        self.assertIn('<tr><th scope="row">Min</th><td>42</td><td>38</td>', page)
        self.assertIn('<tr><th scope="row">Max</th><td>42</td><td>45</td>', page)
        self.assertNotIn('<th scope="row">Value</th>', page)
        self.assertLess(page.index('scope="row">IV'), page.index('scope="row">EV'))
        self.assertLess(page.index('scope="row">EV'), page.index('scope="row">Min'))
        self.assertLess(page.index('scope="row">Min'), page.index('scope="row">Max'))

    def test_marks_a_hidden_ability_in_the_party_card(self) -> None:
        member = _party_member([])
        member["ability"] = {
            "id": 34,
            "name": "Chlorophyll",
            "slug": "chlorophyll",
            "slot": 3,
            "is_hidden": True,
            "source": "derived",
        }

        page = "\n".join(_party_cards([member], "trainers/trainer-0001/"))

        self.assertIn(
            'href="../../abilities/chlorophyll/">Chlorophyll</a>'
            '<abbr class="rw-hidden-ability" title="Hidden Ability">*</abbr>',
            page,
        )


def _party_member(moves: list[str]) -> dict[str, object]:
    return {
        "level": 5,
        "held_item": None,
        "pokemon": {
            "id": 1,
            "name": "Bulbasaur",
            "slug": "bulbasaur",
            "sprite": None,
            "types": [],
        },
        "moves": [{"id": index, "name": name} for index, name in enumerate(moves)],
        "moves_source": "explicit" if moves else "level-up",
        "ability": None,
        "nature": None,
        "gender": None,
        "ivs": None,
        "evs": None,
        "calculated_stats": None,
    }


def _stats(value: int) -> dict[str, int]:
    return {
        "hp": value,
        "attack": value,
        "defense": value,
        "special_attack": value,
        "special_defense": value,
        "speed": value,
    }


def _related_trainer(
    trainer_id: int, location: str, level: int, pokemon: str
) -> dict[str, object]:
    return {
        "trainer_id": trainer_id,
        "class_name": "Ace Trainer",
        "name": "Sam",
        "locations": [{"name": location}],
        "script_references": [],
        "party": [
            {
                "level": level,
                "pokemon": {
                    "id": trainer_id,
                    "name": pokemon,
                    "slug": pokemon.lower(),
                },
                "held_item": None,
                "moves": [],
                "moves_source": "level-up",
                "ability": None,
                "nature": None,
                "gender": None,
                "ivs": None,
                "evs": None,
                "calculated_stats": None,
            }
        ],
    }


if __name__ == "__main__":
    unittest.main()

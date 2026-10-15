from __future__ import annotations

import unittest

import markdown

from romwiki.renderers.mkdocs.trainers.pages import _render_trainer
from romwiki.renderers.mkdocs.trainers.party import _party_gender, party_cards
from romwiki.renderers.mkdocs.trainers.records import group_ai_battle_items
from romwiki.renderers.mkdocs.trainers.rewards import ai_battle_items_section
from romwiki.renderers.mkdocs.trainers.sections import (
    provenance,
    same_name_trainers_section,
)
from romwiki.renderers.mkdocs.trainers.summary import trainer_summary
from romwiki.renderers.mkdocs.trainers.variants import (
    party_section,
    variant_tab_label,
)


class TrainerRenderingTests(unittest.TestCase):
    def test_uses_only_named_public_axes_and_generic_fallback(self) -> None:
        self.assertEqual(
            variant_tab_label(
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
            variant_tab_label(
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
        lines = party_section(
            current,
            [(family, family["variants"][0])],
            {161: current, 162: related},
            "trainers/trainer-0161/",
        )
        page = "\n".join(lines)

        self.assertIn("## Party", page)
        self.assertIn('<div class="tabbed-set tabbed-alternate" data-tabs="1:2">', page)
        self.assertIn('<label for="__tabbed_1_1">Snivy</label>', page)
        self.assertIn('<label for="__tabbed_1_2">Tepig</label>', page)
        self.assertIn('<p>Exact record: <a href="./">trainer-0161</a></p>', page)
        self.assertIn(
            '<p>Exact record: <a href="../trainer-0162/">trainer-0162</a></p>', page
        )
        self.assertNotIn('=== "', page)
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
        lines = party_section(
            current,
            [(family, family["variants"][0])],
            {161: current, 162: related},
            "trainers/trainer-0161/",
        )
        page = "\n".join(lines)

        self.assertNotIn("tabbed-set", page)
        self.assertIn('<p>Selections: <a href="./">Snivy (trainer-0161)</a>', page)
        self.assertIn('<a href="../trainer-0162/">Tepig (trainer-0162)</a></p>', page)
        self.assertEqual(page.count('class="rw-party-grid"'), 1)

    def test_consolidates_location_methods_in_data_provenance(self) -> None:
        lines = provenance(
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
        section = "\n".join(lines)

        self.assertIn('<details class="rw-source-details">', section)
        self.assertIn("<summary>Data provenance</summary>", section)
        self.assertIn(
            "<p>Source: exact ROM trainer record from <code>trdata.narc</code>",
            section,
        )
        self.assertIn("Overworld locations:", section)
        self.assertIn("Scripted battle locations:", section)
        self.assertIn("<code>StartTrainerBattle</code>", section)
        self.assertIn(
            "<tr><td>Unknown byte</td><td><code>0x30</code></td></tr>", section
        )
        self.assertIn("<tr><td>Class gender</td><td>Female</td></tr>", section)
        self.assertIn(
            "ARM9 overlay <code>16</code> at byte offset <code>0x35A00</code>",
            section,
        )
        self.assertNotIn("`", section)

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
        lines = same_name_trainers_section(
            current, [current, related], "trainers/trainer-0005/"
        )
        page = "\n".join(lines)

        self.assertIn("## Same-name trainers", page)
        self.assertNotIn("<details", page)
        self.assertIn("does not establish that they represent the same character", page)
        self.assertIn('<td style="text-align: right;"><code>trainer-0019</code>', page)
        self.assertIn('<a href="../../locations/header-019/">Route 204</a>', page)
        self.assertIn('<a href="../../pokemon/staravia/">Staravia</a>', page)
        self.assertIn('<a href="../../pokemon/machop/">Machop</a>', page)
        self.assertNotIn("more", page)

    def test_renders_each_difficulty_variant_with_its_own_battle_details(self) -> None:
        normal = _related_trainer(156, "Aspertia City", 13, "Lillipup")
        challenge = _related_trainer(764, "Aspertia City", 14, "Lillipup")
        normal.update({"battle_mode": 0, "double_battle": False, "ai_flags": 7})
        challenge.update({"battle_mode": 2, "double_battle": True, "ai_flags": 0xB7})
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
        lines = party_section(
            normal,
            [(family, family["variants"][0])],
            {156: normal, 764: challenge},
            "trainers/trainer-0156/",
        )
        page = "\n".join(lines)

        self.assertIn('<label for="__tabbed_1_1">Easy</label>', page)
        self.assertIn('<label for="__tabbed_1_2">Normal</label>', page)
        self.assertIn('<label for="__tabbed_1_3">Challenge</label>', page)
        self.assertIn("Single battle", page)
        self.assertIn("Triple battle", page)
        self.assertIn("0x000000B7", page)
        self.assertIn("Stored ROM levels", page)
        self.assertIn("may adjust the displayed level by difficulty", page)

    def test_collapses_large_same_name_groups(self) -> None:
        current = _related_trainer(1, "Route 201", 5, "Bidoof")
        related = [
            _related_trainer(trainer_id, "Galactic HQ", 20, "Zubat")
            for trainer_id in range(2, 8)
        ]
        lines = same_name_trainers_section(
            current, [current, *related], "trainers/trainer-0001/"
        )
        page = "\n".join(lines)

        self.assertIn("<details>\n<summary>6 other parties</summary>\n<table>", page)
        self.assertNotIn("markdown=", page)

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
        lines = ai_battle_items_section(
            group_ai_battle_items(record), "trainers/trainer-0005/"
        )
        page = "\n".join(lines)

        self.assertEqual(
            page.count('<a href="../../items/full-restore/">Full Restore</a>'), 1
        )
        self.assertIn('src="https://example.test/full-restore.png"', page)
        self.assertIn('<td style="text-align: right;">2</td>', page)

    def test_omits_empty_ai_battle_item_section(self) -> None:
        self.assertEqual(ai_battle_items_section([], "trainers/test/"), [])

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
            trainer_summary(
                record,
                group_ai_battle_items(record),
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

        page = "\n".join(trainer_summary(record, [], "trainers/trainer-0005/"))

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
            trainer_summary(
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

        page = "\n".join(trainer_summary(record, [], "trainers/trainer-0005/"))

        self.assertIn("<dt>Base prize money</dt><dd>&#8381;2,400</dd>", page)

    def test_numbers_explicit_moves_in_rom_order(self) -> None:
        party = [_party_member(["tackle", "growl"])]

        page = "\n".join(party_cards(party, "trainers/trainer-0001/"))

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

        page = "\n".join(party_cards([member], "trainers/trainer-0001/"))

        self.assertIn("Bulbasaur", page)
        self.assertNotIn("<dt>Nature</dt>", page)
        self.assertNotIn("<dt>Ability</dt>", page)
        self.assertNotIn('<h4 class="rw-party-card__section-title">Stats</h4>', page)

    def test_formats_default_moves_without_a_numbered_slot(self) -> None:
        page = "\n".join(party_cards([_party_member([])], "trainers/trainer-0001/"))

        self.assertNotIn('<ol class="rw-party-card__moves"', page)
        self.assertIn("Uses default level-up moves.", page)

    def test_labels_derived_default_moves(self) -> None:
        member = _party_member(["Tackle", "Growl"])
        member["moves_source"] = "level-up"

        page = "\n".join(party_cards([member], "trainers/trainer-0001/"))

        self.assertIn("Tackle", page)
        self.assertIn("Growl", page)
        self.assertIn(
            '<abbr class="rw-inline-note" title="Derived from the Pokémon\'s '
            'level-up learnset at this level.">*</abbr>',
            page,
        )
        self.assertNotIn("rw-party-card__default-moves", page)

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

        page = "\n".join(party_cards([member], "trainers/trainer-0001/"))

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

        page = "\n".join(party_cards([member], "trainers/trainer-0001/"))

        self.assertIn('<tr><th scope="row">Min</th><td>42</td><td>38</td>', page)
        self.assertIn('<tr><th scope="row">Max</th><td>42</td><td>45</td>', page)
        self.assertNotIn('<th scope="row">Value</th>', page)
        self.assertLess(page.index('scope="row">IV'), page.index('scope="row">EV'))
        self.assertLess(page.index('scope="row">EV'), page.index('scope="row">Min'))
        self.assertLess(page.index('scope="row">Min'), page.index('scope="row">Max'))

    def test_colors_the_natures_boosted_and_lowered_stats(self) -> None:
        member = _party_member([])
        member["nature"] = {"name": "Adamant", "value": 3}
        member["calculated_stats"] = {"source": "derived", "values": _stats(42)}
        member["ivs"] = {"source": "derived", "values": _stats(12)}
        member["evs"] = {"source": "engine-default", "values": _stats(0)}

        page = "\n".join(party_cards([member], "trainers/trainer-0001/"))

        self.assertIn(
            '<tr><th scope="row">Value</th>'
            '<td>42</td><td class="rw-party-card__stat--up">42</td>'
            "<td>42</td>"
            '<td class="rw-party-card__stat--down">42</td>'
            "<td>42</td><td>42</td></tr>",
            page,
        )
        # A nature only affects the calculated stat row, not raw IVs/EVs.
        self.assertIn('<tr><th scope="row">IV</th><td>12</td>', page)
        self.assertNotIn('rw-party-card__stat--up">12', page)

    def test_omits_stat_coloring_for_a_neutral_nature(self) -> None:
        member = _party_member([])
        member["nature"] = {"name": "Hardy", "value": 0}
        member["calculated_stats"] = {"source": "derived", "values": _stats(42)}

        page = "\n".join(party_cards([member], "trainers/trainer-0001/"))

        self.assertNotIn("rw-party-card__stat--up", page)
        self.assertNotIn("rw-party-card__stat--down", page)

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

        page = "\n".join(party_cards([member], "trainers/trainer-0001/"))

        self.assertIn(
            'href="../../abilities/chlorophyll/">Chlorophyll</a>'
            '<abbr class="rw-hidden-ability" title="Hidden Ability">*</abbr>',
            page,
        )

    def test_renders_engine_selected_ability_possibilities(self) -> None:
        member = _party_member([])
        member["ability"] = {
            "slot": 0,
            "source": "engine-default",
            "possibilities": [
                {"id": 1, "name": "Stench", "slug": "stench"},
                {"id": 106, "name": "Aftermath", "slug": "aftermath"},
            ],
        }

        page = "\n".join(party_cards([member], "trainers/trainer-0099/"))

        self.assertIn("<dt>Ability</dt>", page)
        self.assertNotIn("Engine-selected", page)
        self.assertNotIn("(Stench", page)
        self.assertIn('href="../../abilities/stench/">Stench</a>', page)
        self.assertIn("</a> / <a", page)
        self.assertIn('href="../../abilities/aftermath/">Aftermath</a>', page)


class TrainerPageMarkupTests(unittest.TestCase):
    """Whole pages go through Python-Markdown the way MkDocs renders them."""

    _EXTENSIONS = (
        "attr_list",
        "md_in_html",
        "tables",
        "admonition",
        "pymdownx.tabbed",
        "toc",
    )
    _CONFIGS = {
        "pymdownx.tabbed": {"alternate_style": True},
        "toc": {"permalink": True},
    }

    def _convert(self, page: str) -> tuple[str, list[str]]:
        converter = markdown.Markdown(
            extensions=list(self._EXTENSIONS), extension_configs=self._CONFIGS
        )
        html = converter.convert(page)
        headings = [token["id"] for token in _flatten_toc(converter.toc_tokens)]
        return html, headings

    def _family_page(self, change: dict[str, object] | None = None) -> str:
        current = _page_record(161, "Tepig")
        related = _page_record(162, "Oshawott")
        hidden = {
            "id": 66,
            "name": "Blaze",
            "slug": "blaze",
            "is_hidden": True,
        }
        for record in (current, related):
            record["party"][0]["ability"] = hidden  # type: ignore[index]
        family = {
            "id": "rival",
            "order": 0,
            "variants": [
                {
                    "trainer_id": trainer_id,
                    "order": order,
                    "conditions": [{"kind": "starter-choice", "value": starter}],
                }
                for order, (trainer_id, starter) in enumerate(
                    ((161, "snivy"), (162, "tepig"))
                )
            ],
        }
        return _render_trainer(
            current,
            change,
            "Black 2",
            same_name_records=[current, related],
            family_memberships=[(family, family["variants"][0])],
            records_by_id={161: current, 162: related},
        )

    def test_keeps_headings_in_the_toc_and_bodies_as_raw_html(self) -> None:
        html, headings = self._convert(self._family_page())

        self.assertEqual(
            headings,
            [
                "ace-trainer-sam",
                "party",
                "locations",
                "same-name-trainers",
            ],
        )
        self.assertIn('<h2 id="party">Party<a class="headerlink"', html)
        self.assertNotIn("<p><section", html)
        self.assertNotIn("<p><div", html)
        self.assertNotIn("<em>", html)
        self.assertEqual(
            html.count(
                '<abbr class="rw-hidden-ability" title="Hidden Ability">*</abbr>'
            ),
            2,
        )
        self.assertIn('<a href="../trainer-0162/">trainer-0162</a>', html)
        self.assertNotIn(".md", html)

    def test_numbers_party_tabs_after_markdown_comparison_tabs(self) -> None:
        change = {
            "status": "unchanged",
            "version_comparisons": {
                "black-2": {"status": "unchanged"},
                "white-2": {"status": "unchanged"},
            },
        }

        html, headings = self._convert(self._family_page(change))

        self.assertIn("hack-changes", headings)
        self.assertEqual(html.count('data-tabs="1:2"'), 1)
        self.assertEqual(html.count('data-tabs="2:2"'), 1)
        self.assertEqual(html.count('id="__tabbed_1_1"'), 1)
        self.assertEqual(html.count('id="__tabbed_2_1"'), 1)
        self.assertLess(html.index("__tabbed_2_1"), html.index("__tabbed_1_1"))


def _flatten_toc(tokens: list[dict[str, object]]) -> list[dict[str, object]]:
    flattened = []
    for token in tokens:
        flattened.append(token)
        flattened.extend(_flatten_toc(token["children"]))  # type: ignore[arg-type]
    return flattened


def _page_record(trainer_id: int, pokemon: str) -> dict[str, object]:
    record = _related_trainer(trainer_id, "Aspertia City", 5, pokemon)
    record["locations"] = [
        {
            "header_id": 427,
            "name": "Aspertia City",
            "internal_name": "T01",
            "x": 3,
            "z": 9,
            "event_file_id": 427,
            "object_index": 2,
        }
    ]
    record.update(
        {
            "class_id": 1,
            "ai_flags": 0x10,
            "battle_type": 0,
            "double_battle": False,
            "provenance": {"archive": "trdata.narc", "member": trainer_id},
            "party_provenance": {"archive": "trpoke.narc", "member": trainer_id},
        }
    )
    return record


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
        "locations": [{"header_id": trainer_id, "name": location}],
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

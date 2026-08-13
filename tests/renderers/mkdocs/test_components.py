from __future__ import annotations

import json
import unittest

import markdown

from romwiki.pipeline.relationships import MoveLearnerReference
from romwiki.renderers.mkdocs.components import (
    MarkdownColumn,
    class_badge,
    display_name,
    effectiveness_table_cell,
    effectiveness_value,
    evolution_condition,
    fact_grid,
    markdown_section,
    markdown_table,
    markdown_table_from_cells,
    provenance_section,
    record_nav_link,
    record_navigation,
    summary_section_link,
    tutor_requirement,
    type_badges,
)
from romwiki.renderers.mkdocs.items import _party_effects
from romwiki.renderers.mkdocs.moves import (
    _egg_move_learners,
    _pokemon_sprite_table,
    _pokemon_table_link,
    _reference_effects_section,
    _relationship_learner_table,
    _tutor_compatibility,
)
from romwiki.renderers.mkdocs.references import EntityReference, ReferenceIndex


class DisplayNameTests(unittest.TestCase):
    def test_preserves_domain_specific_capitalization(self) -> None:
        expected_names = {
            "poke-balls": "Poké Balls",
            "poke-radar": "Poké Radar",
            "tm-hm": "TM / HM",
            "vs-recorder": "Vs. Recorder",
            "vs-seeker": "Vs. Seeker",
        }

        for value, expected in expected_names.items():
            with self.subTest(value=value):
                self.assertEqual(display_name(value), expected)

    def test_title_cases_regular_slug(self) -> None:
        self.assertEqual(display_name("evolution-stone"), "Evolution Stone")


class TutorRequirementTests(unittest.TestCase):
    def test_formats_battle_point_costs(self) -> None:
        self.assertEqual(
            tutor_requirement({"kind": "battle-points", "battle_point_cost": 40}),
            "40 BP",
        )
        self.assertEqual(
            tutor_requirement({"kind": "battle-points", "battle_point_cost": 0}),
            "Free",
        )


class EvolutionConditionTests(unittest.TestCase):
    def test_links_party_species_parameter(self) -> None:
        entry = {
            "method": {"id": 21, "name": "level-with-party-species"},
            "parameter_data": {
                "kind": "pokemon",
                "id": 224,
                "slug": "remoraid",
                "name": "Remoraid",
            },
        }

        condition = evolution_condition(entry, "pokemon/mantyke/")

        self.assertEqual(
            condition,
            'Level up with <a href="../remoraid/">Remoraid</a> in the party',
        )


class ComponentEscapingTests(unittest.TestCase):
    def test_type_badges_are_presentational(self) -> None:
        badges = type_badges([{"name": "fire"}])

        self.assertEqual(
            badges,
            '<span class="rw-type-list">'
            '<span class="rw-type rw-type--fire">Fire</span>'
            "</span>",
        )
        self.assertNotIn("<a ", badges)

    def test_effectiveness_values_share_semantic_states(self) -> None:
        quarter = effectiveness_value("1/4")
        half = effectiveness_value("1/2")
        double = effectiveness_value("2")
        quadruple = effectiveness_value("4")

        self.assertIn("rw-effectiveness--resisted", quarter)
        self.assertIn("rw-effectiveness--strong", quarter)
        self.assertIn("One-quarter effectiveness: ¼×", quarter)
        self.assertNotIn("rw-effectiveness--strong", half)
        self.assertNotIn("rw-effectiveness--strong", double)
        self.assertIn("rw-effectiveness--effective", quadruple)
        self.assertIn("rw-effectiveness--strong", quadruple)
        self.assertIn("Four-times effectiveness: 4×", quadruple)
        self.assertIn("<strong>4×</strong>", quadruple)
        self.assertIn(
            "rw-effectiveness--resisted rw-effectiveness--strong",
            effectiveness_table_cell("1/4"),
        )
        self.assertEqual(
            effectiveness_table_cell("4"),
            '<td class="rw-effectiveness rw-effectiveness--effective '
            'rw-effectiveness--strong" aria-label="Four-times effectiveness: '
            '4×"><strong>4×</strong></td>',
        )

    def test_escapes_text_and_attribute_values(self) -> None:
        hostile = 'fire" onmouseover="alert(1)&<script>'

        self.assertNotIn("<script>", type_badges([{"name": hostile}]))
        self.assertNotIn("<script>", class_badge({"name": hostile}))
        self.assertIn("A&amp;B", "".join(fact_grid((("A&B", "<value>"),))))
        self.assertIn("&lt;value&gt;", "".join(fact_grid((("A&B", "<value>"),))))
        link = record_nav_link('next/" onclick="alert(1)', "A < B", "next")
        self.assertIn("&quot; onclick=&quot;", link)
        self.assertIn("A &lt; B", link)
        self.assertEqual(
            summary_section_link("A & B", 'facts" onclick="alert(1)'),
            '<a href="#facts&quot; onclick=&quot;alert(1)">A &amp; B</a>',
        )


class MarkdownTableTests(unittest.TestCase):
    def test_preserves_rendered_lines_and_adds_one_trailing_blank(self) -> None:
        lines = markdown_table(
            ("| Name | Value |", "| ---- | ----: |"),
            (row for row in ("| A | 1 |", "| B | 2 |")),
        )

        self.assertEqual(
            lines,
            [
                "| Name | Value |",
                "| ---- | ----: |",
                "| A | 1 |",
                "| B | 2 |",
                "",
            ],
        )

    def test_renders_full_table_without_collapsing(self) -> None:
        rows = [f"| Row {i} |" for i in range(120)]

        lines = markdown_table(["| Col |", "| --- |"], rows)

        rendered = "\n".join(lines)
        self.assertNotIn("<details", rendered)
        self.assertIn("Row 119", rendered)

    def test_column_specification_owns_headers_and_alignment(self) -> None:
        lines = markdown_table_from_cells(
            (
                MarkdownColumn("Pokémon"),
                MarkdownColumn("Levels", "right"),
                MarkdownColumn("Chance", "right"),
            ),
            (("<a>Bulbasaur</a>", "5–7", "20%"),),
        )

        self.assertEqual(
            lines,
            [
                "| Pokémon | Levels | Chance |",
                "| ------- | -----: | -----: |",
                "| <a>Bulbasaur</a> | 5–7 | 20% |",
                "",
            ],
        )

    def test_column_specification_rejects_wrong_row_width(self) -> None:
        with self.assertRaisesRegex(ValueError, "1 cells; expected 2"):
            markdown_table_from_cells(
                (MarkdownColumn("Name"), MarkdownColumn("Value")),
                (("Bulbasaur",),),
            )


class MarkdownSectionTests(unittest.TestCase):
    def test_frames_pre_rendered_body_without_rewriting_it(self) -> None:
        lines = markdown_section(
            "Details",
            ("Raw **Markdown** and <span>HTML</span>.", ""),
            level=3,
        )

        self.assertEqual(
            lines,
            [
                "### Details",
                "",
                "Raw **Markdown** and <span>HTML</span>.",
                "",
            ],
        )

    def test_empty_body_keeps_heading_separation(self) -> None:
        self.assertEqual(markdown_section("Details", ()), ["## Details", ""])

    def test_rejects_invalid_heading_level(self) -> None:
        with self.assertRaisesRegex(ValueError, "between 1 and 6"):
            markdown_section("Details", (), level=7)


class DisclosureAndNavigationContractTests(unittest.TestCase):
    def test_provenance_disclosure_has_stable_markdown_nesting(self) -> None:
        lines = provenance_section(["Source: exact ROM record."])

        self.assertEqual(
            lines,
            [
                '<details class="rw-source-details" markdown="1">',
                "<summary>Data provenance</summary>",
                "",
                "Source: exact ROM record.",
                "",
                "</details>",
                "",
            ],
        )
        rendered = markdown.markdown("\n".join(lines), extensions=["md_in_html"])
        self.assertIn('<details class="rw-source-details">', rendered)
        self.assertIn("<summary>Data provenance</summary>", rendered)

    def test_previous_next_navigation_preserves_empty_side_and_trailing_blank(
        self,
    ) -> None:
        lines = record_navigation(None, '<a href="next/">Next →</a>', "Navigation")

        self.assertEqual(
            lines,
            [
                '<nav class="rw-record-nav" aria-label="Navigation">',
                "<span></span>",
                '<a href="next/">Next →</a>',
                "</nav>",
                "",
            ],
        )


class MoveReferenceSectionTests(unittest.TestCase):
    def test_metadata_only_effects_do_not_skip_a_heading_level(self) -> None:
        section = _reference_effects_section(
            {"reference": {"metadata": {"flinch_chance": 30}}}
        )

        self.assertEqual(section[0], "## Additional effects")

    def test_effect_metadata_is_nested_under_effect_prose(self) -> None:
        section = _reference_effects_section(
            {
                "reference": {
                    "short_effect": "May cause flinching.",
                    "metadata": {"flinch_chance": 30},
                }
            }
        )

        self.assertEqual(section[0], "### Additional effects")

    def test_large_learner_tables_can_omit_repetitive_sprites(self) -> None:
        link = _pokemon_table_link(
            {"id": 1, "name": "Bulbasaur", "slug": "bulbasaur"},
            "moves/test.md",
            None,
            False,
        )

        self.assertEqual(link, "[Bulbasaur](../pokemon/bulbasaur.md)")

    def test_small_learner_tables_show_sprites_uncollapsed(self) -> None:
        pokemon = [
            {"id": i, "name": f"Species {i}", "slug": f"species-{i}"}
            for i in range(1, 51)
        ]

        lines = _pokemon_sprite_table(pokemon, "moves/test.md", None, "None.")

        rendered = "\n".join(lines)
        self.assertIn("rw-table-sprite", rendered)
        self.assertNotIn("data-rw-learner-table", rendered)
        self.assertNotIn("<details", rendered)

    def test_large_learner_tables_paginate_with_complete_sprite_free_fallback(
        self,
    ) -> None:
        pokemon = [
            {"member": i, "name": f"Species {i}", "slug": f"species-{i}"}
            for i in range(1, 52)
        ]
        references = ReferenceIndex(
            EntityReference(
                "pokemon",
                i,
                f"Species {i}",
                f"species-{i}",
                f"https://example.test/sprites/{i}.png",
                ({"name": "grass"},),
            )
            for i in range(1, 52)
        )

        lines = _pokemon_sprite_table(pokemon, "moves/test.md", references, "None.")

        rendered = "\n".join(lines)
        self.assertNotIn("<details", rendered)
        self.assertIn("data-rw-learner-table", rendered)
        self.assertNotIn("rw-table-sprite", rendered)
        self.assertIn("Species 51", rendered)
        payload = json.loads(
            rendered.split(
                '<script type="application/json" data-rw-learner-data>\n', 1
            )[1].split("\n</script>", 1)[0]
        )
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["page_size"], 50)
        self.assertEqual(len(payload["rows"]), 51)
        self.assertEqual(payload["rows"][0][0]["url"], "../../pokemon/species-1/")
        self.assertEqual(
            payload["rows"][0][0]["sprite_url"],
            "https://example.test/sprites/1.png",
        )
        fallback = rendered.split("data-rw-learner-fallback", 1)[1]
        self.assertIn("[Species 51](../pokemon/species-51.md)", fallback)
        self.assertNotIn("<img", fallback)
        html = markdown.markdown(rendered, extensions=["md_in_html", "tables"])
        self.assertIn("<table>", html)
        self.assertIn("Species 51", html)
        self.assertNotIn("<img", html)

    def test_large_relationship_learner_tables_use_distinct_page_state(self) -> None:
        for detail, expected_param in (
            ("level", "level_page"),
            ("machine", "machine_page"),
        ):
            learners = tuple(
                MoveLearnerReference(
                    move_id=1,
                    pokemon_id=i,
                    pokemon_name=f"Species {i}",
                    pokemon_slug=f"species-{i}",
                    pokemon_form=None,
                    method="level-up" if detail == "level" else "machine",
                    level=i if detail == "level" else None,
                    machine_id=None if detail == "level" else 1,
                    machine_name=None if detail == "level" else "TM01",
                    machine_kind=None if detail == "level" else "tm",
                    versions=("black",),
                )
                for i in range(1, 52)
            )

            rendered = "\n".join(
                _relationship_learner_table(
                    learners, "moves/test.md", None, detail=detail
                )
            )

            with self.subTest(detail=detail):
                self.assertIn(f'"page_param":"{expected_param}"', rendered)
                self.assertIn("Species 51", rendered)
                self.assertNotIn("rw-table-sprite", rendered)

    def test_tutor_and_egg_tables_use_distinct_page_state(self) -> None:
        pokemon = [
            {"id": i, "name": f"Species {i}", "slug": f"species-{i}"}
            for i in range(1, 52)
        ]
        record = {
            "tutors": [
                {
                    "kind": "special",
                    "minimum_friendship": 255,
                    "location": {"name": "Test Lab"},
                    "compatible_pokemon": pokemon,
                }
            ],
            "egg_move_pokemon": pokemon,
        }

        tutor = "\n".join(_tutor_compatibility(record, "moves/test.md", None))
        egg = "\n".join(_egg_move_learners(record, "moves/test.md", None))

        self.assertIn('"page_param":"tutor_1_page"', tutor)
        self.assertIn('"page_param":"egg_page"', egg)
        self.assertNotIn("rw-table-sprite", tutor)
        self.assertNotIn("rw-table-sprite", egg)

    def test_learner_payload_cannot_close_its_script_element(self) -> None:
        pokemon = [
            {
                "id": i,
                "name": f"Species </script><script>{i}",
                "slug": f"species-{i}",
            }
            for i in range(1, 52)
        ]

        rendered = "\n".join(
            _pokemon_sprite_table(pokemon, "moves/test.md", None, "None.")
        )

        payload = rendered.split(
            '<script type="application/json" data-rw-learner-data>\n', 1
        )[1].split("\n</script>", 1)[0]
        self.assertNotIn("</script>", payload)
        self.assertIn(r"\u003c/script\u003e", payload)


class ItemPartyEffectTests(unittest.TestCase):
    def test_includes_stat_ev_friendship_and_guard_effects(self) -> None:
        effects = dict.fromkeys(
            (
                "heal_sleep",
                "heal_poison",
                "heal_burn",
                "heal_freeze",
                "heal_paralysis",
                "heal_confusion",
                "heal_attract",
                "guard_spec",
                "revive",
                "revive_all",
                "level_up",
                "evolve",
                "pp_up",
                "pp_max",
                "pp_restore",
                "pp_restore_all",
                "hp_restore",
                "hp_ev",
                "attack_ev",
                "defense_ev",
                "speed_ev",
                "special_attack_ev",
                "special_defense_ev",
                "friendship_low",
                "friendship_medium",
                "friendship_high",
            ),
            False,
        )
        effects.update(
            {
                "guard_spec": True,
                "attack_stages": 2,
                "defense_stages": 0,
                "special_attack_stages": 0,
                "special_defense_stages": 0,
                "speed_stages": 0,
                "accuracy_stages": 0,
                "critical_hit_stages": 0,
                "hp_ev": True,
                "hp_ev_amount": 10,
                "attack_ev_amount": 0,
                "defense_ev_amount": 0,
                "speed_ev_amount": 0,
                "special_attack_ev_amount": 0,
                "special_defense_ev_amount": 0,
                "friendship_low": True,
                "friendship_low_amount": 5,
                "friendship_medium_amount": 0,
                "friendship_high_amount": 0,
                "hp_restored": 0,
                "pp_restored": 0,
            }
        )

        rendered = _party_effects({"party_use": True, "party_effects": effects})

        self.assertIn("prevents stat reduction", rendered)
        self.assertIn("Attack +2 stages", rendered)
        self.assertIn("HP EVs +10", rendered)
        self.assertIn("friendship (low +5)", rendered)


if __name__ == "__main__":
    unittest.main()

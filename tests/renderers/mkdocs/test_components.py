from __future__ import annotations

import unittest

from romwiki.renderers.mkdocs.components import (
    class_badge,
    display_name,
    evolution_condition,
    fact_grid,
    pokemon_table,
    record_nav_link,
    summary_section_link,
    type_badges,
)
from romwiki.renderers.mkdocs.items import _party_effects
from romwiki.renderers.mkdocs.moves import (
    _pokemon_sprite_table,
    _pokemon_table_link,
    _reference_effects_section,
)


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


class PokemonTableTests(unittest.TestCase):
    def test_renders_full_table_without_collapsing(self) -> None:
        rows = [f"| Row {i} |" for i in range(120)]

        lines = pokemon_table(["| Col |", "| --- |"], rows)

        rendered = "\n".join(lines)
        self.assertNotIn("<details", rendered)
        self.assertIn("Row 119", rendered)


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
        pokemon = [{"id": 1, "name": "Bulbasaur", "slug": "bulbasaur"}]

        lines = _pokemon_sprite_table(pokemon, "moves/test.md", None, "None.")

        rendered = "\n".join(lines)
        self.assertIn("rw-table-sprite", rendered)
        self.assertNotIn("<details", rendered)

    def test_large_learner_tables_render_in_full_without_collapsing(self) -> None:
        pokemon = [
            {"id": i, "name": f"Species {i}", "slug": f"species-{i}"}
            for i in range(1, 52)
        ]

        lines = _pokemon_sprite_table(pokemon, "moves/test.md", None, "None.")

        rendered = "\n".join(lines)
        self.assertNotIn("<details", rendered)
        self.assertIn("rw-table-sprite", rendered)
        self.assertIn("Species 51", rendered)


class ItemPartyEffectTests(unittest.TestCase):
    def test_includes_stat_ev_friendship_and_guard_effects(self) -> None:
        effects = dict.fromkeys(("heal_sleep", "heal_poison", "heal_burn", "heal_freeze", "heal_paralysis", "heal_confusion", "heal_attract", "guard_spec", "revive", "revive_all", "level_up", "evolve", "pp_up", "pp_max", "pp_restore", "pp_restore_all", "hp_restore", "hp_ev", "attack_ev", "defense_ev", "speed_ev", "special_attack_ev", "special_defense_ev", "friendship_low", "friendship_medium", "friendship_high"), False)
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

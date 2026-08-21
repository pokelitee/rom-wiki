from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from romwiki.pipeline.enrichment.pokemon import enrich_personal_dataset
from romwiki.pipeline.enrichment.type_charts import build_type_dataset
from romwiki.profiles.loader import ProfileRepository
from romwiki.renderers.mkdocs import render_pokemon_pages
from romwiki.renderers.mkdocs.pokemon import (
    _evolution_list,
    _index_preevolutions,
    _sprite_gallery,
)
from romwiki.sources import PokeDBGeneration

FORM_SPECIES = {
    "deoxys-attack": "deoxys",
    "deoxys-defense": "deoxys",
    "deoxys-speed": "deoxys",
    "wormadam-sandy": "wormadam",
    "wormadam-trash": "wormadam",
    "giratina-origin": "giratina",
    "shaymin-sky": "shaymin",
    "rotom-heat": "rotom",
    "rotom-wash": "rotom",
    "rotom-frost": "rotom",
    "rotom-fan": "rotom",
    "rotom-mow": "rotom",
}


class PersonalEnrichmentTests(unittest.TestCase):
    def test_maps_public_species_forms_and_internal_records(self) -> None:
        defaults = {
            pokemon_id: {
                "id": pokemon_id,
                "name": f"pokemon-{pokemon_id}",
                "species": f"pokemon-{pokemon_id}",
            }
            for pokemon_id in range(1, 494)
        }
        for pokemon_id, species in (
            (386, "deoxys"),
            (413, "wormadam"),
            (479, "rotom"),
            (487, "giratina"),
            (492, "shaymin"),
        ):
            defaults[pokemon_id] = {
                "id": pokemon_id,
                "name": f"{species}-default",
                "species": species,
            }
        variants = {
            name: {"id": 10000 + index, "name": name, "species": species}
            for index, (name, species) in enumerate(FORM_SPECIES.items())
        }
        by_name = {item["name"]: item for item in defaults.values()}
        by_name.update(variants)
        pokedb = PokeDBGeneration(
            pokemon_by_id=defaults,
            pokemon_by_name=by_name,
            pokemon_by_species={item["species"]: item for item in defaults.values()},
            abilities_by_id={65: "overgrow"},
            items_by_id={},
        )
        records = [_source_record(member) for member in range(508)]
        records[1]["type_ids"] = [9, 9]
        records[1]["ability_ids"] = [65, 65]
        ability_names = [f"Ability {ability_id}" for ability_id in range(124)]
        ability_names[65] = "Overgrow"
        pokemon_names = ["-----"] + [f"Rom-{index}" for index in range(1, 496)]
        pokemon_names[1] = "MR. MIME"
        pokemon_names[494] = "Egg"
        pokemon_names[495] = "Bad Egg"

        enriched = enrich_personal_dataset(
            {
                "game": "test",
                "engine": "gen4_platinum",
                "source": {"archive": "personal.narc"},
                "ability_names": ability_names,
                "pokemon_names": pokemon_names,
                "records": records,
            },
            pokedb,
            type_names={9: "fairy"},
        )
        hgss_enriched = enrich_personal_dataset(
            {
                "game": "test",
                "engine": "gen4_hgss",
                "source": {"archive": "a/0/0/2"},
                "ability_names": ability_names,
                "pokemon_names": pokemon_names,
                "records": records,
            },
            pokedb,
            type_names={9: "fairy"},
        )

        self.assertEqual(enriched["public_record_count"], 505)
        self.assertFalse(enriched["records"][494]["public"])
        self.assertEqual(enriched["records"][496]["slug"], "deoxys-attack")
        self.assertEqual(enriched["records"][496]["national_dex_id"], 386)
        self.assertEqual(enriched["records"][1]["types"][0], {"id": 9, "name": "fairy"})
        self.assertEqual(
            enriched["records"][1]["abilities"][0],
            {"id": 65, "slug": "overgrow", "name": "Overgrow", "is_hidden": False},
        )
        # ROM names win for regular species (recapitalized from vanilla caps);
        # form members keep their slug-derived form labels.
        self.assertEqual(enriched["records"][1]["name"], "Mr. Mime")
        self.assertEqual(enriched["records"][2]["name"], "Rom-2")
        self.assertEqual(enriched["records"][496]["name"], "Deoxys Attack")
        self.assertEqual(hgss_enriched["public_record_count"], 505)
        self.assertEqual(hgss_enriched["records"][496]["slug"], "deoxys-attack")

    def test_resolves_gen5_alternate_formes_and_battle_only_transformations(
        self,
    ) -> None:
        defaults = {
            pokemon_id: {
                "id": pokemon_id,
                "name": f"pokemon-{pokemon_id}",
                "species": f"pokemon-{pokemon_id}",
            }
            for pokemon_id in range(1, 650)
        }
        for pokemon_id, name, species in (
            (386, "deoxys", "deoxys"),
            (413, "wormadam", "wormadam"),
            (487, "giratina", "giratina"),
            (492, "shaymin", "shaymin"),
            (479, "rotom", "rotom"),
            (550, "basculin", "basculin"),
            (351, "castform", "castform"),
            (555, "darmanitan-standard", "darmanitan"),
            (648, "meloetta-aria", "meloetta"),
        ):
            defaults[pokemon_id] = {"id": pokemon_id, "name": name, "species": species}
        gen5_form_species = {
            "deoxys-attack": "deoxys",
            "deoxys-defense": "deoxys",
            "deoxys-speed": "deoxys",
            "wormadam-sandy": "wormadam",
            "wormadam-trash": "wormadam",
            "shaymin-sky": "shaymin",
            "giratina-origin": "giratina",
            "rotom-heat": "rotom",
            "rotom-wash": "rotom",
            "rotom-frost": "rotom",
            "rotom-fan": "rotom",
            "rotom-mow": "rotom",
            "basculin-blue-striped": "basculin",
        }
        variants = {
            name: {"id": 10000 + index, "name": name, "species": species}
            for index, (name, species) in enumerate(gen5_form_species.items())
        }
        by_name = {item["name"]: item for item in defaults.values()}
        by_name.update(variants)
        pokedb = PokeDBGeneration(
            pokemon_by_id=defaults,
            pokemon_by_name=by_name,
            pokemon_by_species={item["species"]: item for item in defaults.values()},
            abilities_by_id={},
            items_by_id={},
        )
        records = [_source_record(member) for member in range(668)]

        enriched = enrich_personal_dataset(
            {
                "game": "test",
                "engine": "gen5_bw",
                "source": {"archive": "personal.narc"},
                "records": records,
            },
            pokedb,
            type_names={0: "normal"},
        )

        deoxys_attack = enriched["records"][650]
        self.assertTrue(deoxys_attack["public"])
        self.assertEqual(deoxys_attack["slug"], "deoxys-attack")
        self.assertEqual(deoxys_attack["national_dex_id"], 386)

        castform_sunny = enriched["records"][662]
        self.assertFalse(castform_sunny["public"])
        self.assertNotIn("battle_forms", castform_sunny)

        castform = enriched["records"][351]
        self.assertEqual(
            [form["label"] for form in castform["battle_forms"]],
            ["Sunny Form", "Rainy Form", "Snowy Form"],
        )
        self.assertEqual(
            castform["battle_forms"][0]["base_stats"], castform_sunny["base_stats"]
        )

        darmanitan = enriched["records"][555]
        self.assertEqual(
            [form["label"] for form in darmanitan["battle_forms"]], ["Zen Mode"]
        )

        meloetta = enriched["records"][648]
        self.assertEqual(
            [form["label"] for form in meloetta["battle_forms"]], ["Pirouette Forme"]
        )

    def test_renders_a_page_and_index(self) -> None:
        record = _bulbasaur_record()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            count = render_pokemon_pages(
                {"engine": "gen4_hgss", "records": [record]}, output
            )
            page = (output / "bulbasaur.md").read_text(encoding="utf-8")
            catalog = json.loads((output / "catalog.json").read_text(encoding="utf-8"))

        self.assertEqual(count, 1)
        self.assertIn("# Bulbasaur", page)
        self.assertEqual(page.count("rw-type--grass"), 1)
        self.assertIn('<span class="rw-stat__value">45</span>', page)
        self.assertNotIn("+5", page)
        self.assertIn("A seed was planted on its back at birth.", page)
        self.assertIn(
            '<audio class="rw-summary__cry" controls preload="none" '
            'src="https://example.test/bulbasaur.ogg">',
            page,
        )
        self.assertNotIn("rw-summary__credit", page)
        self.assertIn("<div><dt>Body color</dt><dd>Green</dd></div>", page)
        self.assertIn("<div><dt>Habitat</dt><dd>Grassland</dd></div>", page)
        self.assertIn("<div><dt>Shape</dt><dd>Quadruped</dd></div>", page)
        self.assertNotIn('rw-summary__tag">', page)
        self.assertIn("0.7 m (2′4″)", page)
        self.assertIn("1 Sp. Atk", page)
        self.assertIn("87.5% male / 12.5% female", page)
        self.assertNotIn("Base typing", page)
        self.assertIn("[Tackle](../moves/tackle.md)", page)
        self.assertIn("[Skull Bash](../moves/skull-bash.md)", page)
        self.assertIn("| Move | Type | Class | Power | Accuracy | PP |", page)
        self.assertIn("## Learnset", page)
        self.assertIn("`0x29222`", page)
        self.assertIn('<a href="../ivysaur/">Ivysaur</a>', page)
        self.assertIn('<span class="rw-record-tree__name">', page)
        self.assertIn("Level 16", page)
        self.assertIn(
            'Use <a href="../../items/kings-rock/">King&#x27;s Rock</a>', page
        )
        self.assertIn("[Focus Punch](../moves/focus-punch.md)", page)
        self.assertIn("## Wild held items", page)
        self.assertIn(
            '| Rare | <span class="rw-cell-media">'
            '<span class="rw-table-sprite rw-table-sprite--empty" '
            'aria-hidden="true">—</span>Moon Stone</span> | 81 |',
            page,
        )
        self.assertIn("[Seed Bomb](../moves/seed-bomb.md)", page)
        self.assertIn("4 Red, 4 Green", page)
        self.assertIn("[Frenzy Plant](../moves/frenzy-plant.md)", page)
        self.assertIn("Friendship 255", page)
        self.assertEqual(catalog["schema_version"], 5)
        self.assertEqual(catalog["kind"], "pokemon")
        self.assertEqual(catalog["records"][0]["bst"], 318)
        self.assertEqual(catalog["records"][0]["trainer_count"], 0)
        self.assertEqual(
            catalog["records"][0]["availability_methods"],
            ["no-known-direct-source"],
        )
        self.assertEqual(catalog["records"][0]["wild_location_count"], 0)
        self.assertNotIn("wild_obtainable", catalog["records"][0])
        self.assertNotIn("minimum_obtainable_level", catalog["records"][0])
        self.assertEqual(catalog["records"][0]["egg_groups"], ["monster", "grass"])
        self.assertEqual(catalog["records"][0]["url"], "bulbasaur/")

    def test_pokemon_learnset_sections_follow_explicit_features(self) -> None:
        black_record = _bulbasaur_record()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            render_pokemon_pages(
                {"records": [black_record], "features": ["egg-moves"]},
                output,
            )
            black_page = (output / "bulbasaur.md").read_text(encoding="utf-8")

        self.assertNotIn("### Move tutors", black_page)
        self.assertNotIn("[Seed Bomb]", black_page)
        self.assertIn("### Egg moves", black_page)
        self.assertIn("[Skull Bash]", black_page)

        b2w2_record = _bulbasaur_record()
        b2w2_record["tutor_moves"] = []
        b2w2_record["egg_moves"] = []
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            render_pokemon_pages(
                {
                    "records": [b2w2_record],
                    "features": ["egg-moves", "move-tutors"],
                },
                output,
            )
            b2w2_page = (output / "bulbasaur.md").read_text(encoding="utf-8")

        self.assertIn("### Move tutors", b2w2_page)
        self.assertIn("No compatible tutor moves.", b2w2_page)
        self.assertIn("### Egg moves", b2w2_page)
        self.assertIn("No egg moves.", b2w2_page)

    def test_unsupported_egg_moves_omit_section_and_provenance(self) -> None:
        record = _bulbasaur_record()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            render_pokemon_pages({"records": [record], "features": []}, output)
            page = (output / "bulbasaur.md").read_text(encoding="utf-8")

        self.assertNotIn("### Egg moves", page)
        self.assertNotIn("Egg move source", page)
        self.assertNotIn("`0x29222`", page)

    def test_renders_classification_badges_for_legendary_and_baby_species(self) -> None:
        record = _bulbasaur_record()
        record["reference"]["is_legendary"] = True
        record["reference"]["is_baby"] = True
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            render_pokemon_pages({"records": [record]}, output)
            page = (output / "bulbasaur.md").read_text(encoding="utf-8")

        self.assertIn(
            '<div class="rw-summary__badges">'
            '<span class="rw-type-list"><span class="rw-type rw-type--grass">Grass</span></span>'
            '<span class="rw-summary__tag">Legendary</span>'
            '<span class="rw-summary__tag">Baby</span></div>',
            page,
        )
        self.assertNotIn(">Mythical<", page)

    def test_renders_defensive_type_effectiveness(self) -> None:
        record = _bulbasaur_record()
        record["types"].append({"id": 3, "name": "poison"})
        profile = next(
            profile
            for profile in ProfileRepository.load(Path("profiles")).profiles
            if profile.id == "renegade-platinum"
        )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            render_pokemon_pages(
                {"records": [record]},
                output,
                type_dataset=build_type_dataset(profile),
            )
            page = (output / "bulbasaur.md").read_text(encoding="utf-8")

        self.assertIn("## Type effectiveness", page)
        self.assertIn(
            'class="rw-effectiveness__value rw-effectiveness--resisted"',
            page,
        )
        self.assertIn("One-quarter effectiveness: ¼×", page)
        self.assertNotIn('href="../../types/#', page)
        self.assertNotIn(
            "type effectiveness", page.split("## Type effectiveness", 1)[1]
        )
        self.assertNotIn("| 1× |", page)
        self.assertLess(
            page.index("## Base stats"), page.index("## Type effectiveness")
        )
        self.assertLess(page.index("## Type effectiveness"), page.index("## Training"))

    def test_renders_four_times_defensive_effectiveness(self) -> None:
        record = _bulbasaur_record()
        record["types"] = [
            {"id": 11, "name": "water"},
            {"id": 3, "name": "flying"},
        ]
        profile = next(
            profile
            for profile in ProfileRepository.load(Path("profiles")).profiles
            if profile.id == "renegade-platinum"
        )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            render_pokemon_pages(
                {"records": [record]},
                output,
                type_dataset=build_type_dataset(profile),
            )
            page = (output / "bulbasaur.md").read_text(encoding="utf-8")

        self.assertIn(
            'class="rw-effectiveness__value rw-effectiveness--effective"',
            page,
        )
        self.assertIn("Four-times effectiveness: 4×", page)
        self.assertIn("<strong>4×</strong>", page)

    def test_renders_battle_only_forms_section_when_present(self) -> None:
        record = _bulbasaur_record()
        record["battle_forms"] = [
            {
                "label": "Sunny Form",
                "base_stats": {
                    "hp": 70,
                    "attack": 70,
                    "defense": 70,
                    "speed": 70,
                    "special_attack": 70,
                    "special_defense": 70,
                },
                "types": [{"id": 9, "name": "fire"}],
            }
        ]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            render_pokemon_pages({"records": [record]}, output)
            page = (output / "bulbasaur.md").read_text(encoding="utf-8")

        self.assertIn("## Battle-only forms", page)
        self.assertIn("### Sunny Form", page)
        self.assertIn("rw-type--fire", page)
        self.assertEqual(page.count('<span class="rw-stat__value">70</span>'), 6)

    def test_omits_battle_only_forms_section_when_absent(self) -> None:
        record = _bulbasaur_record()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            render_pokemon_pages({"records": [record]}, output)
            page = (output / "bulbasaur.md").read_text(encoding="utf-8")

        self.assertNotIn("Battle-only forms", page)

    def test_labels_the_hidden_ability_slot(self) -> None:
        record = _bulbasaur_record()
        record["abilities"] = [
            {"id": 65, "slug": "overgrow", "name": "Overgrow", "is_hidden": False},
            {"id": 0, "slug": None, "name": None, "is_hidden": False},
            {"id": 34, "slug": "chlorophyll", "name": "Chlorophyll", "is_hidden": True},
        ]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            render_pokemon_pages({"records": [record]}, output)
            page = (output / "bulbasaur.md").read_text(encoding="utf-8")
            catalog = json.loads((output / "catalog.json").read_text(encoding="utf-8"))

        self.assertIn(
            "<div><dt>Abilities</dt><dd>"
            '<a href="../../abilities/overgrow/">Overgrow</a>, '
            '<a href="../../abilities/chlorophyll/">Chlorophyll</a>'
            '<abbr class="rw-hidden-ability" title="Hidden Ability">*</abbr>'
            "</dd></div>",
            page,
        )
        refs = catalog["records"][0]["ability_refs"]
        self.assertEqual([ref["label"] for ref in refs], ["Overgrow", "Chlorophyll"])
        self.assertNotIn("hidden", refs[0])
        self.assertTrue(refs[1]["hidden"])

    def test_only_pages_skips_detail_pages_but_keeps_full_catalog(self) -> None:
        record = _bulbasaur_record()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            count = render_pokemon_pages(
                {"records": [record]}, output, only_pages=frozenset()
            )
            catalog = json.loads((output / "catalog.json").read_text(encoding="utf-8"))

        self.assertEqual(count, 0)
        self.assertFalse((output / "bulbasaur.md").exists())
        self.assertEqual(len(catalog["records"]), 1)
        self.assertEqual(catalog["records"][0]["slug"], "bulbasaur")

    def test_indexes_reverse_evolution_links_for_public_records(self) -> None:
        records = [
            {
                "public": True,
                "member": 1,
                "national_dex_id": 1,
                "slug": "bulbasaur",
                "name": "Bulbasaur",
                "evolutions": [
                    {
                        "method_id": 4,
                        "target": {
                            "id": 2,
                            "slug": "ivysaur",
                            "name": "Ivysaur",
                        },
                    }
                ],
            },
            {
                "public": True,
                "member": 2,
                "national_dex_id": 2,
                "slug": "ivysaur",
                "name": "Ivysaur",
                "evolutions": [],
            },
        ]

        index = _index_preevolutions(records)

        self.assertEqual(index["ivysaur"][0]["source"]["slug"], "bulbasaur")
        self.assertEqual(index["ivysaur"][0]["evolution"]["method_id"], 4)

    def test_renders_complete_branching_evolution_chain(self) -> None:
        eevee = _evolution_record("eevee", "Eevee", 133)
        vaporeon = _evolution_record("vaporeon", "Vaporeon", 134)
        jolteon = _evolution_record("jolteon", "Jolteon", 135)
        eevee["evolutions"] = [
            _evolution("vaporeon", "Vaporeon", 134, "Water Stone"),
            _evolution("jolteon", "Jolteon", 135, "Thunder Stone"),
        ]

        chain = "\n".join(
            _evolution_list([eevee, vaporeon, jolteon], jolteon, "pokemon/jolteon.md")
        )

        self.assertIn("Eevee", chain)
        self.assertIn("Vaporeon", chain)
        self.assertIn("Jolteon", chain)
        self.assertIn("Water Stone", chain)
        self.assertIn('aria-current="page"', chain)
        self.assertIn('class="rw-record-tree__current">Current', chain)
        self.assertIn('class="rw-record-tree__dex">#135', chain)
        self.assertIn("rw-record-tree__row--child", chain)
        self.assertIn('href="../vaporeon/"', chain)

    def test_renders_personality_based_branch_as_a_level_not_a_branch_number(
        self,
    ) -> None:
        wurmple = _evolution_record("wurmple", "Wurmple", 265)
        silcoon = _evolution_record("silcoon", "Silcoon", 266)
        cascoon = _evolution_record("cascoon", "Cascoon", 268)
        wurmple["evolutions"] = [
            {
                "method_id": 11,
                "method": {"id": 11, "name": "level-personality-low"},
                "parameter_data": {"kind": "personality", "value": 7},
                "target": {"id": 266, "slug": "silcoon", "name": "Silcoon"},
            },
            {
                "method_id": 12,
                "method": {"id": 12, "name": "level-personality-high"},
                "parameter_data": {"kind": "personality", "value": 7},
                "target": {"id": 268, "slug": "cascoon", "name": "Cascoon"},
            },
        ]

        chain = "\n".join(
            _evolution_list([wurmple, silcoon, cascoon], wurmple, "pokemon/wurmple.md")
        )

        self.assertIn("Level 7 (random — low personality value)", chain)
        self.assertIn("Level 7 (random — high personality value)", chain)
        self.assertNotIn("personality branch", chain)


class SpriteGalleryTests(unittest.TestCase):
    def test_renders_empty_state_when_no_sprites_are_available(self) -> None:
        expected = ["## Sprites", "", "No sprites are available.", ""]
        self.assertEqual(
            _sprite_gallery({"name": "Missingno", "sprites": []}), expected
        )
        self.assertEqual(_sprite_gallery({"name": "Missingno"}), expected)

    def test_still_renders_a_single_known_sprite(self) -> None:
        lines = _sprite_gallery(
            {
                "name": "Bulbasaur",
                "sprites": [
                    {
                        "key": "front_default",
                        "label": "Front",
                        "url": "https://example.test/front.png",
                    }
                ],
            }
        )

        page = "\n".join(lines)
        self.assertIn("## Sprites", page)
        self.assertIn('src="https://example.test/front.png"', page)
        self.assertIn('<span class="rw-sprite-matrix__label">Front</span>', page)

    def test_groups_variants_into_a_normal_and_shiny_matrix(self) -> None:
        lines = _sprite_gallery(
            {
                "name": "Bulbasaur",
                "sprites": [
                    {
                        "key": "front_default",
                        "label": "Front",
                        "url": "https://example.test/front.png",
                    },
                    {
                        "key": "front_shiny",
                        "label": "Front, shiny",
                        "url": "https://example.test/front-shiny.png",
                    },
                    {
                        "key": "back_default",
                        "label": "Back",
                        "url": "https://example.test/back.png",
                    },
                ],
            }
        )

        page = "\n".join(lines)
        self.assertIn('<span class="rw-sprite-matrix__label">Front</span>', page)
        self.assertIn('<span class="rw-sprite-matrix__label">Back</span>', page)
        self.assertNotIn("Front, female", page)
        self.assertIn('src="https://example.test/front.png"', page)
        self.assertIn('src="https://example.test/front-shiny.png"', page)
        self.assertIn('src="https://example.test/back.png"', page)
        self.assertIn('rw-sprite-matrix__cell--empty">—<', page)
        self.assertNotIn("Animated", page)
        self.assertNotIn("rw-sprite-matrix--animated", page)

    def test_adds_an_animated_column_only_when_animated_sprites_exist(self) -> None:
        lines = _sprite_gallery(
            {
                "name": "Bulbasaur",
                "sprites": [
                    {
                        "key": "front_default",
                        "label": "Front",
                        "url": "https://example.test/front.png",
                    },
                    {
                        "key": "front_shiny",
                        "label": "Front, shiny",
                        "url": "https://example.test/front-shiny.png",
                    },
                    {
                        "key": "front_default_animated",
                        "label": "Front, animated",
                        "url": "https://example.test/front.gif",
                    },
                ],
            }
        )

        page = "\n".join(lines)
        self.assertIn("rw-sprite-matrix rw-sprite-matrix--animated", page)
        self.assertIn("<span>Animated</span><span>Animated, shiny</span>", page)
        self.assertIn('src="https://example.test/front.gif"', page)
        self.assertEqual(page.count("rw-sprite-matrix__cell--empty"), 1)


def _bulbasaur_record() -> dict:
    return {
        "public": True,
        "member": 1,
        "slug": "bulbasaur",
        "name": "Bulbasaur",
        "national_dex_id": 1,
        "form": None,
        "reference": {
            "version": "platinum",
            "source": "PokéDB / PokéAPI",
            "source_url": "https://pokeapi.co/api/v2/pokemon/1/",
            "genus": "Seed Pokémon",
            "height_dm": 7,
            "weight_hg": 69,
            "flavor_text": "A seed was planted on its back at birth.",
            "flavor_text_version": "platinum",
            "base_stats": {
                "hp": 45,
                "attack": 49,
                "defense": 49,
                "speed": 45,
                "special_attack": 60,
                "special_defense": 65,
            },
            "types": ["grass", "poison"],
            "abilities": ["overgrow"],
            "is_baby": False,
            "is_legendary": False,
            "is_mythical": False,
            "habitat": "grassland",
            "shape": "quadruped",
        },
        "body_color": {"id": 3, "name": "green"},
        "cry": {
            "key": "legacy",
            "url": "https://example.test/bulbasaur.ogg",
            "source": "PokéAPI cries",
            "source_url": "https://github.com/PokeAPI/cries",
        },
        "base_stats": {
            "hp": 45,
            "attack": 49,
            "defense": 49,
            "speed": 45,
            "special_attack": 65,
            "special_defense": 65,
        },
        "types": [{"name": "grass"}, {"name": "grass"}],
        "abilities": [{"name": "overgrow"}],
        "catch_rate": 45,
        "base_experience": 64,
        "base_friendship": 70,
        "ev_yields": {
            "hp": 0,
            "attack": 0,
            "defense": 0,
            "speed": 0,
            "special_attack": 1,
            "special_defense": 0,
        },
        "gender_ratio": 31,
        "safari_flee_rate": 0,
        "hatch_cycles": 20,
        "growth_rate": {"name": "medium-slow"},
        "egg_groups": [{"name": "monster"}, {"name": "grass"}],
        "held_items": [
            {"rarity": "common", "id": 0, "name": None},
            {"rarity": "rare", "id": 81, "name": "Moon Stone"},
        ],
        "machines": [
            {
                "name": "TM01",
                "move": {"id": 264, "slug": "focus-punch", "name": "Focus Punch"},
            }
        ],
        "tutor_moves": [
            {
                "move": {"id": 402, "slug": "seed-bomb", "name": "Seed Bomb"},
                "location": {"id": 1, "name": "Survival Area"},
                "shard_costs": {"red": 4, "blue": 0, "yellow": 0, "green": 4},
            },
            {
                "kind": "special",
                "move": {
                    "id": 338,
                    "slug": "frenzy-plant",
                    "name": "Frenzy Plant",
                },
                "location": {"name": "Route 228"},
                "minimum_friendship": 255,
            },
        ],
        "level_up_moves": [
            {
                "level": 1,
                "move": {"id": 33, "slug": "tackle", "name": "Tackle"},
            }
        ],
        "egg_moves": [{"id": 130, "slug": "skull-bash", "name": "Skull Bash"}],
        "egg_move_provenance": {"overlay_offset": 0x29222, "table_index": 0},
        "learnset_provenance": {"archive": "wotbl.narc", "member": 1},
        "evolutions": [
            {
                "method_id": 4,
                "method": {"id": 4, "name": "level"},
                "parameter_data": {"kind": "level", "value": 16},
                "target": {"id": 2, "slug": "ivysaur", "name": "Ivysaur"},
            },
            {
                "method_id": 7,
                "method": {"id": 7, "name": "use-item"},
                "parameter_data": {
                    "kind": "item",
                    "id": 221,
                    "name": "King's Rock",
                    "slug": "kings-rock",
                },
                "target": {"id": 2, "slug": "ivysaur", "name": "Ivysaur"},
            },
        ],
        "evolution_provenance": {"archive": "evo.narc", "member": 1},
        "flip_sprite": False,
        "provenance": {"archive": "personal.narc", "member": 1},
    }


def _source_record(member: int) -> dict:
    return {
        "species_id": member,
        "base_stats": {
            "hp": 1,
            "attack": 1,
            "defense": 1,
            "speed": 1,
            "special_attack": 1,
            "special_defense": 1,
        },
        "type_ids": [0, 0],
        "catch_rate": 1,
        "base_experience": 1,
        "ev_yields": {
            "hp": 0,
            "attack": 0,
            "defense": 0,
            "speed": 0,
            "special_attack": 0,
            "special_defense": 0,
        },
        "wild_held_items": {"common": 0, "rare": 0},
        "gender_ratio": 255,
        "hatch_cycles": 1,
        "base_friendship": 1,
        "growth_rate_id": 0,
        "egg_group_ids": [0, 0],
        "ability_ids": [0, 0],
        "safari_flee_rate": 0,
        "body_color_id": 10 if member in {494, 495} else 0,
        "flip_sprite": False,
        "machine_ids": [],
        "provenance": {"source": "rom", "archive": "personal.narc", "member": member},
    }


def _evolution_record(slug: str, name: str, member: int) -> dict:
    return {
        "slug": slug,
        "name": name,
        "member": member,
        "national_dex_id": member,
        "sprite": None,
        "evolutions": [],
    }


def _evolution(slug: str, name: str, member: int, item: str) -> dict:
    return {
        "method_id": 7,
        "method": {"id": 7, "name": "use-item"},
        "parameter_data": {"kind": "item", "id": 1, "name": item},
        "target": {"id": member, "slug": slug, "name": name},
    }


if __name__ == "__main__":
    unittest.main()

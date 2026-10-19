from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from romwiki.sites.data_exports import write_public_dataset
from romwiki.sites.frontend import (
    DETAIL_CHUNK_SIZE,
    _encounter_facets,
    _evolution_chains,
    _index_record,
    _index_sprite,
    _search_text,
    _with_record_slugs,
    export_frontend,
    record_route,
)
from romwiki.sites.frontend_snapshot import (
    create_frontend_snapshot,
    restore_frontend_snapshot,
)
from romwiki.util.errors import DataSourceError, SiteError


def make_repository(root: Path) -> Path:
    for kind, identifier in (("portal", "portal"), ("game", "test-game")):
        directory = (
            root / "sites" / ("portal" if kind == "portal" else "games/test-game")
        )
        directory.mkdir(parents=True)
        descriptor = directory / ("site.toml" if kind == "portal" else "game.toml")
        descriptor.write_text(
            f'[site]\nid="{identifier}"\nname="Test"\nkind="{kind}"\n'
            f'slug="{"" if kind == "portal" else identifier}"\npublished=true\norder=0\n'
            '[appearance]\ntheme="platinum"\n'
            + (
                '[game]\nprofile="test-game"\ngeneration=4\nbase_game="test-game"\n'
                'platform="nintendo-ds"\nplatform_name="Nintendo DS"\ncreator="Test"\n'
                if kind == "game"
                else ""
            ),
            encoding="utf-8",
        )
    wiki = root / "sites/games/test-game/wiki"
    wiki.mkdir()
    (wiki / "index.md").write_text(
        '# Test game\n\n--8<-- "shared.md"\n', encoding="utf-8"
    )
    partials = root / "sites/shared/partials"
    partials.mkdir(parents=True)
    (partials / "shared.md").write_text("Supported mechanics.\n", encoding="utf-8")
    return wiki


def pokemon_dataset(count: int = 1) -> dict:
    return {
        "dataset": "pokemon",
        "schema_version": 1,
        "game": "test-game",
        "record_count": count,
        "features": ["egg-moves"],
        "source": {"source": "synthetic"},
        "records": [
            {
                "member": number,
                "national_dex_id": number,
                "name": f"Pokemon {number}",
                "slug": f"pokemon-{number}",
                "base_stats": {"hp": 45},
                "public": True,
            }
            for number in range(1, count + 1)
        ],
    }


def test_export_is_deterministic_chunked_and_rom_free() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        wiki = make_repository(root)
        write_public_dataset(wiki, "pokemon", pokemon_dataset(DETAIL_CHUNK_SIZE + 1))
        output = root / "export"
        assert export_frontend(root, output) == 1
        first = {
            p.relative_to(output): p.read_bytes()
            for p in output.rglob("*")
            if p.is_file()
        }
        export_frontend(root, output)
        assert first == {
            p.relative_to(output): p.read_bytes()
            for p in output.rglob("*")
            if p.is_file()
        }
        manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
        game = manifest["games"][0]
        index = json.loads(
            (output / game["sections"]["pokemon"]["index"]).read_text(encoding="utf-8")
        )
        assert len({row["chunk"] for row in index["records"]}) == 2
        assert game["sections"]["pokemon"]["metadata"]["features"] == ["egg-moves"]
        doc = json.loads(
            (output / game["documents"][0]["path"]).read_text(encoding="utf-8")
        )
        assert "Supported mechanics." in doc["markdown"]
        assert not list(output.rglob("*.html"))


def test_export_titles_guides_counts_published_records_and_adds_sprites() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        wiki = make_repository(root)
        dataset = pokemon_dataset(2)
        dataset["records"][0]["sprite"] = {"url": "https://example.test/1.png"}
        dataset["records"].append(
            {"member": 0, "name": "Egg", "slug": "egg", "public": False}
        )
        dataset["record_count"] = 3
        write_public_dataset(wiki, "pokemon", dataset)
        docs = wiki / "docs"
        docs.mkdir()
        (docs / "faq.md").write_text("---\ntitle: FAQ\n---\n\n## Q\n")
        (docs / "special_events.md").write_text("## Events\n")
        (docs / "index.md").write_text("Official notes.\n")
        output = root / "export"
        export_frontend(root, output)

        manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
        game = manifest["games"][0]
        assert [document["label"] for document in game["documents"]] == [
            "Index",
            "FAQ",
            "Special events",
            "Test game",
        ]
        faq = json.loads((output / game["documents"][1]["path"]).read_text())
        assert faq["markdown"] == "\n## Q\n"
        pokemon = game["sections"]["pokemon"]
        assert pokemon["metadata"]["record_count"] == 3
        assert pokemon["metadata"]["published_count"] == 2
        index = json.loads((output / pokemon["index"]).read_text(encoding="utf-8"))
        assert [row.get("sprite") for row in index["records"]] == [
            "https://example.test/1.png",
            None,
        ]


def test_index_labels_unnamed_areas_and_carries_item_sprites() -> None:
    record = {"name": "－" * 10, "header_id": 151}
    assert _index_record("locations", record, "header-151")["label"] == (
        "Unnamed area (header-151)"
    )
    assert (
        _index_sprite(
            "items", {"reference": {"sprite_url": "https://example.test/i.png"}}
        )
        == "https://example.test/i.png"
    )
    assert _index_sprite("moves", {"sprite": {"url": "x"}}) is None


def test_export_publishes_the_game_mascot_sprite() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        wiki = make_repository(root)
        descriptor = root / "sites/games/test-game/game.toml"
        descriptor.write_text(
            descriptor.read_text(encoding="utf-8").replace(
                '[appearance]\ntheme="platinum"\n',
                '[appearance]\ntheme="platinum"\nmascot="pokemon-1"\n',
            ),
            encoding="utf-8",
        )
        dataset = pokemon_dataset(1)
        dataset["records"][0]["sprite"] = {"url": "https://example.test/1.png"}
        write_public_dataset(wiki, "pokemon", dataset)
        output = root / "export"
        export_frontend(root, output)
        game = json.loads((output / "manifest.json").read_text(encoding="utf-8"))[
            "games"
        ][0]
        assert game["mascot"] == {
            "name": "Pokemon 1",
            "sprite": "https://example.test/1.png",
        }

        dataset["records"][0].pop("sprite")
        write_public_dataset(wiki, "pokemon", dataset)
        with pytest.raises(SiteError, match="mascot has no published sprite"):
            export_frontend(root, root / "export-2")


def test_export_publishes_the_portal_mascot_from_a_game() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        wiki = make_repository(root)
        portal = root / "sites/portal/site.toml"
        portal.write_text(
            portal.read_text(encoding="utf-8").replace(
                '[appearance]\ntheme="platinum"\n',
                '[appearance]\ntheme="platinum"\nmascot="pokemon-2"\n',
            ),
            encoding="utf-8",
        )
        dataset = pokemon_dataset(2)
        dataset["records"][1]["sprite"] = {"url": "https://example.test/2.png"}
        write_public_dataset(wiki, "pokemon", dataset)
        output = root / "export"
        export_frontend(root, output)
        manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["mascot"] == {
            "name": "Pokemon 2",
            "sprite": "https://example.test/2.png",
        }


def test_export_rejects_corrupt_archives_and_duplicate_routes() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        wiki = make_repository(root)
        dataset = pokemon_dataset()
        dataset["records"].append(dataset["records"][0])
        write_public_dataset(wiki, "pokemon", dataset)
        with pytest.raises(DataSourceError, match="failed content checks"):
            export_frontend(root, root / "output")
        # Locations have no content checks, so their duplicates reach routing.
        write_public_dataset(wiki, "pokemon", pokemon_dataset())
        locations = {
            "dataset": "locations",
            "schema_version": 1,
            "game": "test-game",
            "record_count": 2,
            "source": {"source": "synthetic"},
            "records": [{"header_id": 1, "name": "Route 1"}] * 2,
        }
        write_public_dataset(wiki, "locations", locations)
        with pytest.raises(SiteError, match="Duplicate frontend identity"):
            export_frontend(root, root / "output")
        (wiki / "data/pokemon.json.gz").write_bytes(b"invalid")
        with pytest.raises(SiteError, match="Invalid public data archive"):
            export_frontend(root, root / "output")


def test_comparative_site_requires_explicit_comparison_outputs() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        wiki = make_repository(root)
        descriptor = wiki.parent / "game.toml"
        descriptor.write_text(
            descriptor.read_text().replace(
                'base_game="test-game"', 'base_game="baseline"'
            )
        )
        write_public_dataset(wiki, "pokemon", pokemon_dataset())
        with pytest.raises(SiteError, match="Missing test-game pokemon comparison"):
            export_frontend(root, root / "output")


def test_document_includes_cannot_escape_the_partials_directory() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        wiki = make_repository(root)
        (wiki / "index.md").write_text('--8<-- "../../../secret"\n')
        write_public_dataset(wiki, "pokemon", pokemon_dataset())
        with pytest.raises(SiteError, match="Invalid or recursive"):
            export_frontend(root, root / "output")


def test_typed_routes_preserve_conditional_sources() -> None:
    assert record_route("trainers", {"trainer_id": 3}) == "trainer-0003"
    assert record_route("locations", {"header_id": 3}) == "header-003"
    assert record_route("encounters", {"area_id": 3}) == "area-003"
    assert (
        record_route(
            "encounters", {"source_type": "headbutt", "location": {"header_id": 3}}
        )
        == "headbutt-003"
    )


def test_search_text_matches_frontend_lowercasing() -> None:
    # web/src/lib/utils.test.ts expects the same output from searchText.
    assert (
        _search_text("Straße ÉCLAIR İstanbul ΟΔΟΣ ﬁre")
        == "straße éclair i̇stanbul οδος ﬁre"
    )


def test_frontend_snapshot_round_trip_and_corruption_rejection() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        wiki = make_repository(root)
        write_public_dataset(wiki, "pokemon", pokemon_dataset())
        source, snapshot, restored = (
            root / "export",
            root / "snapshot",
            root / "restored",
        )
        export_frontend(root, source)
        archive = create_frontend_snapshot(source, snapshot)
        first = archive.read_bytes()
        assert create_frontend_snapshot(source, snapshot).read_bytes() == first
        assert restore_frontend_snapshot(snapshot, restored) > 0
        assert (restored / "manifest.json").read_bytes() == (
            source / "manifest.json"
        ).read_bytes()
        archive.write_bytes(first[:-10])
        with pytest.raises(SiteError, match="checksum mismatch"):
            restore_frontend_snapshot(snapshot, root / "invalid")
        assert not (root / "invalid").exists()


def test_version_variants_and_supported_empty_sections_are_preserved() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        wiki = make_repository(root)
        dataset = pokemon_dataset()
        dataset["records"][0].update(
            egg_moves=[],
            version_variants={"second-version": {"base_stats": {"hp": 65}}},
        )
        write_public_dataset(wiki, "pokemon", dataset)
        output = root / "output"
        export_frontend(root, output)
        manifest = json.loads((output / "manifest.json").read_text())
        section = manifest["games"][0]["sections"]["pokemon"]
        index = json.loads((output / section["index"]).read_text())
        chunk = json.loads((output / index["records"][0]["chunk"]).read_text())
        assert chunk["pokemon-1"]["record"] == dataset["records"][0]
        assert section["metadata"]["features"] == ["egg-moves"]


def test_item_and_species_references_gain_their_page_slug() -> None:
    value = {
        "items": [{"item_id": 17, "name": "Potion"}, {"item_id": 999, "name": "X"}],
        "item": {"item_id": 17, "slug": "potion", "name": "Potion"},
        "static_encounters": [{"name": "Raikou", "species_id": 243}],
        "trades": [{"name": "Route 15", "pokemon": {"id": 373, "name": "Salamence"}}],
    }
    assert _with_record_slugs(
        value, {17: "potion"}, {243: "raikou", 373: "salamence"}
    ) == {
        "items": [
            {"item_id": 17, "name": "Potion", "item_slug": "potion"},
            {"item_id": 999, "name": "X"},
        ],
        "item": {"item_id": 17, "slug": "potion", "name": "Potion"},
        "static_encounters": [
            {"name": "Raikou", "species_id": 243, "pokemon_slug": "raikou"}
        ],
        "trades": [
            {
                "name": "Route 15",
                "pokemon": {"id": 373, "name": "Salamence", "slug": "salamence"},
            }
        ],
    }


def test_encounter_level_ranges_skip_empty_slots() -> None:
    record = {
        "walking": {
            "slots": [
                {"level": 30, "pokemon": {"name": "Geodude"}},
                {"level": 0, "pokemon": None},
            ]
        },
        "radar": {"slots": [{"level": 39, "pokemon": {"name": "Machoke"}}]},
    }
    facets = _encounter_facets(record)
    assert (facets["min_level"], facets["max_level"]) == (30, 39)


def _species(
    slug: str, dex: int, *targets: str, member: int | None = None
) -> dict[str, object]:
    return {
        "slug": slug,
        "name": slug.title(),
        "national_dex_id": dex,
        "member": dex if member is None else member,
        "evolutions": [
            {"method": {"name": "level"}, "parameter": 7, "target": {"slug": target}}
            for target in targets
        ],
    }


def test_evolution_chains_cover_the_whole_branching_family() -> None:
    chains = _evolution_chains(
        [
            _species("wurmple", 265, "silcoon", "cascoon"),
            _species("silcoon", 266, "beautifly"),
            _species("beautifly", 267),
            _species("cascoon", 268, "dustox"),
            _species("dustox", 269),
            _species("wormadam", 413),
            _species("wormadam-sandy", 413, member=496),
            _species("burmy", 412, "wormadam"),
            _species("ditto", 132),
        ]
    )

    def shape(node: dict[str, object]) -> object:
        steps = node["evolutions"]
        assert isinstance(steps, list)
        return {node["slug"]: [shape(step["target"]) for step in steps]}

    wurmple = {
        "wurmple": [{"silcoon": [{"beautifly": []}]}, {"cascoon": [{"dustox": []}]}]
    }
    assert shape(chains["dustox"]) == wurmple
    assert chains["wurmple"] == chains["beautifly"]
    assert chains["wurmple"]["evolutions"][0]["method"] == {"name": "level"}
    # Alternate forms share their base form's family.
    assert shape(chains["wormadam-sandy"]) == {"burmy": [{"wormadam": []}]}
    assert "ditto" not in chains

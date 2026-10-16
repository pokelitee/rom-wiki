from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from romwiki.sites.data_exports import write_public_dataset
from romwiki.sites.frontend import (
    DETAIL_CHUNK_SIZE,
    _index_record,
    _index_sprite,
    _search_text,
    export_frontend,
    record_route,
)
from romwiki.sites.frontend_snapshot import (
    create_frontend_snapshot,
    restore_frontend_snapshot,
)
from romwiki.util.errors import SiteError


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
            "Test game",
            "Index",
            "FAQ",
            "Special events",
        ]
        faq = json.loads((output / game["documents"][2]["path"]).read_text())
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


def test_export_rejects_corrupt_archives_and_duplicate_routes() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        wiki = make_repository(root)
        dataset = pokemon_dataset()
        dataset["records"].append(dataset["records"][0])
        write_public_dataset(wiki, "pokemon", dataset)
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

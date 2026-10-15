from __future__ import annotations

import json
from pathlib import Path

import pytest

from romwiki.sites.data_exports import write_public_dataset
from romwiki.sites.frontend import export_frontend
from romwiki.util.errors import SiteError
from scripts.check_frontend_publication import check_publication
from tests.sites.test_frontend import make_repository, pokemon_dataset


@pytest.fixture
def publication(tmp_path: Path) -> Path:
    wiki = make_repository(tmp_path)
    descriptor = wiki.parent / "game.toml"
    descriptor.write_text(
        descriptor.read_text().replace(
            "[game]\n", '[game]\ngenerated_sections=["pokemon","types"]\n'
        )
    )
    (wiki / "data-sources.md").write_text("# Data sources\nSynthetic test data.\n")
    write_public_dataset(wiki, "pokemon", pokemon_dataset())
    write_public_dataset(
        wiki,
        "types",
        {
            "dataset": "types",
            "game": "test-game",
            "schema_version": 1,
            "record_count": 0,
            "records": [],
        },
    )
    output = tmp_path / "publication"
    export_frontend(tmp_path, output)
    return output


def test_complete_publication_matches_catalog(publication: Path) -> None:
    assert check_publication(publication.parent, publication) == 1


@pytest.mark.parametrize(
    ("missing", "message"),
    [
        ("game", "published game catalog"),
        ("section", "section coverage"),
        ("guide", "reference guides"),
        ("record", "Missing frontend record"),
    ],
)
def test_incomplete_publication_is_rejected(
    publication: Path, missing: str, message: str
) -> None:
    output = publication
    path = output / "manifest.json"
    manifest = json.loads(path.read_text())
    game = manifest["games"][0]
    if missing == "game":
        manifest["games"] = []
    elif missing == "section":
        game["sections"] = {}
    elif missing == "guide":
        game["documents"] = [{"id": "index"}, {"id": "other"}]
    else:
        index = json.loads((output / game["sections"]["pokemon"]["index"]).read_text())
        (output / index["records"][0]["chunk"]).write_text("{}")
    path.write_text(json.dumps(manifest))
    with pytest.raises(SiteError, match=message):
        check_publication(publication.parent, output)


def test_comparative_game_requires_comparison_data(publication: Path) -> None:
    descriptor = publication.parent / "sites/games/test-game/game.toml"
    descriptor.write_text(
        descriptor.read_text().replace('base_game="test-game"', 'base_game="baseline"')
    )
    with pytest.raises(SiteError, match="Missing frontend comparison"):
        check_publication(publication.parent, publication)

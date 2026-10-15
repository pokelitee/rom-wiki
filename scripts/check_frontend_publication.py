"""Check that restored publication data covers the repository's published games."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from romwiki.sites.catalog import SiteCatalog
from romwiki.util.errors import SiteError

ROOT = Path(__file__).resolve().parents[1]


def check_publication(root: Path, publication: Path) -> int:
    manifest = json.loads((publication / "manifest.json").read_text(encoding="utf-8"))
    games = manifest["games"]
    expected = {
        site.id: site
        for site in SiteCatalog.load(root).published()
        if site.kind == "game"
    }
    if len(games) != len(expected) or {game["id"] for game in games} != set(expected):
        raise SiteError(
            "Frontend publication does not match the published game catalog"
        )
    for game in games:
        site = expected[game["id"]]
        assert site.game is not None
        if set(game["sections"]) != set(site.game.generated_sections):
            raise SiteError(f"Frontend section coverage mismatch: {site.id}")
        if not {"index", "data-sources"} <= {doc["id"] for doc in game["documents"]}:
            raise SiteError(f"Missing frontend reference guides: {site.id}")
        for section, descriptor in game["sections"].items():
            index = json.loads(
                (publication / descriptor["index"]).read_text(encoding="utf-8")
            )
            chunks: dict[str, dict] = {}
            for row in index["records"]:
                if row["chunk"] not in chunks:
                    chunks[row["chunk"]] = json.loads(
                        (publication / row["chunk"]).read_text(encoding="utf-8")
                    )
                if row["id"] not in chunks[row["chunk"]]:
                    raise SiteError(f"Missing frontend record: {site.id}/{section}")
            if (
                site.game.base_game != site.id
                and section != "types"
                and section not in game["comparisons"]
            ):
                raise SiteError(f"Missing frontend comparison: {site.id}/{section}")
    return len(games)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--publication", type=Path, default=ROOT / "web/public/data")
    args = parser.parse_args()
    count = check_publication(args.root, args.publication)
    print(f"Verified complete frontend publication for {count} games")


if __name__ == "__main__":
    main()

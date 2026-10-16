"""Create synthetic, ROM-free browser-test data; never use this for publication."""

from __future__ import annotations

import tempfile
from pathlib import Path

from romwiki.sites.data_exports import write_public_dataset
from romwiki.sites.frontend import export_frontend


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="romwiki-browser-fixture-") as directory:
        root = Path(directory)
        for kind, relative, identifier in (
            ("portal", "portal", "portal"),
            ("game", "games/platinum", "platinum"),
        ):
            path = root / "sites" / relative
            path.mkdir(parents=True)
            (path / ("site.toml" if kind == "portal" else "game.toml")).write_text(
                f'[site]\nid="{identifier}"\nname="Pokémon Platinum"\nkind="{kind}"\n'
                f'slug="{"" if kind == "portal" else identifier}"\npublished=true\norder=0\n'
                '[appearance]\ntheme="platinum"\n'
                + (
                    '[game]\nprofile="synthetic"\ngeneration=4\nbase_game="platinum"\n'
                    'platform="nintendo-ds"\nplatform_name="Nintendo DS"\ncreator="Synthetic test fixture"\n'
                    if kind == "game"
                    else ""
                ),
                encoding="utf-8",
            )
        wiki = root / "sites/games/platinum/wiki"
        wiki.mkdir()
        (wiki / "index.md").write_text(
            "# Synthetic browser-test fixture\n", encoding="utf-8"
        )
        (wiki / "data-sources.md").write_text(
            "# Data sources\n\nSynthetic data; no ROM inputs.\n", encoding="utf-8"
        )
        write_public_dataset(
            wiki,
            "pokemon",
            {
                "dataset": "pokemon",
                "game": "synthetic",
                "engine": "synthetic",
                "schema_version": 1,
                "features": [],
                "record_count": 1,
                "source": {"source": "synthetic"},
                "records": [
                    {
                        "member": 1,
                        "national_dex_id": 1,
                        "slug": "bulbasaur",
                        "name": "Bulbasaur",
                        "public": True,
                        "base_stats": {
                            "hp": 45,
                            "attack": 49,
                            "defense": 49,
                            "special_attack": 65,
                            "special_defense": 65,
                            "speed": 45,
                        },
                        "types": [{"id": 12, "name": "grass"}],
                        "abilities": [
                            {
                                "id": 65,
                                "is_hidden": False,
                                "name": "Overgrow",
                                "slug": "overgrow",
                            }
                        ],
                        "level_up_moves": [
                            {
                                "level": 1,
                                "move": {"id": 33, "name": "Tackle", "slug": "tackle"},
                            }
                        ],
                        "egg_groups": [],
                    }
                ],
            },
        )
        for kind, record in (
            ("abilities", {"id": 65, "slug": "overgrow", "name": "Overgrow"}),
            ("moves", {"id": 33, "slug": "tackle", "name": "Tackle", "power": 35}),
        ):
            write_public_dataset(
                wiki,
                kind,
                {
                    "dataset": kind,
                    "game": "synthetic",
                    "engine": "synthetic",
                    "schema_version": 1,
                    "features": [],
                    "record_count": 1,
                    "source": {"source": "synthetic"},
                    "records": [record],
                },
            )
        export_frontend(root, Path("web/public/data"))


if __name__ == "__main__":
    main()

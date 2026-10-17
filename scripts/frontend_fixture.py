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
                "record_count": 2,
                "source": {"source": "synthetic"},
                "records": [
                    {
                        "member": 1,
                        "national_dex_id": 1,
                        "slug": "bulbasaur",
                        "name": "Bulbasaur",
                        "public": True,
                        "gender_ratio": 31,
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
                        "evolutions": [
                            {
                                "method": {"id": 4, "name": "level"},
                                "parameter": 16,
                                "target": {
                                    "id": 2,
                                    "name": "Ivysaur",
                                    "slug": "ivysaur",
                                },
                            }
                        ],
                        "egg_groups": [],
                    },
                    {
                        "member": 2,
                        "national_dex_id": 2,
                        "slug": "ivysaur",
                        "name": "Ivysaur",
                        "public": True,
                        "types": [{"id": 12, "name": "grass"}],
                    },
                ],
            },
        )
        for kind, record in (
            ("abilities", {"id": 65, "slug": "overgrow", "name": "Overgrow"}),
            ("moves", {"id": 33, "slug": "tackle", "name": "Tackle", "power": 35}),
            (
                "trainers",
                {
                    "trainer_id": 1,
                    "class_name": "Leader",
                    "name": "Roark",
                    "ai_battle_items": [
                        {"id": 17, "name": "Potion", "slug": "potion"},
                        {"id": 17, "name": "Potion", "slug": "potion"},
                    ],
                    "party": [
                        {
                            "level": 12,
                            "pokemon": {
                                "id": 1,
                                "name": "Bulbasaur",
                                "slug": "bulbasaur",
                            },
                            "ability": {
                                "id": 65,
                                "name": "Overgrow",
                                "slug": "overgrow",
                            },
                            "held_item": None,
                            "nature": {"name": "Lax"},
                            "gender": {"name": "Male"},
                            "moves": [
                                {
                                    "id": 33,
                                    "name": "tackle",
                                    "slug": "tackle",
                                    "type": {"id": 0, "name": "normal"},
                                    "damage_class": {"id": 1, "name": "physical"},
                                }
                            ],
                            "calculated_stats": {
                                "values": {"hp": 32, "attack": 24, "speed": 10}
                            },
                            "ivs": {"values": {"hp": 6, "attack": 6, "speed": 6}},
                            "evs": {"values": {"hp": 0, "attack": 0, "speed": 0}},
                        }
                    ],
                },
            ),
            (
                "encounters",
                {
                    "area_id": 0,
                    "name": "Route 201",
                    "walking": {
                        "rate": 30,
                        "slots": [
                            {
                                "chance": 20,
                                "level": 2,
                                "pokemon": {
                                    "id": 1,
                                    "name": "Bulbasaur",
                                    "slug": "bulbasaur",
                                },
                            },
                            {
                                "chance": 10,
                                "level": 3,
                                "pokemon": {
                                    "id": 1,
                                    "name": "Bulbasaur",
                                    "slug": "bulbasaur",
                                },
                            },
                        ],
                    },
                    "good_rod": {
                        "rate": 0,
                        "slots": [{"chance": 40, "minimum_level": 0, "pokemon": None}],
                    },
                },
            ),
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

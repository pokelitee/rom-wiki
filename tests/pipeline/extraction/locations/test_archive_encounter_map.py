from __future__ import annotations

import unittest
from types import SimpleNamespace

from romwiki.engines.gen5.bw.overworld import resolve_common_script_member
from romwiki.pipeline.extraction.locations.archive_script_references import (
    extract_script_awarded_items,
    resolve_script_locations,
)
from romwiki.pipeline.transforms.relationships import build_relationship_index


class _Archive:
    def __init__(self, member_count: int) -> None:
        self.members = (None,) * member_count

    @staticmethod
    def read(index: int) -> bytes:
        return bytes((index,))


class Gen5ScriptLocationTests(unittest.TestCase):
    def test_links_script_awards_to_each_proven_script_owner(self) -> None:
        award = SimpleNamespace(
            item_id=17,
            quantity=2,
            command_offset=12,
            command="ItemAdd",
        )
        engine = SimpleNamespace(
            find_script_awarded_items=lambda _data, item_count: (award,)
        )

        references = extract_script_awarded_items(
            engine,
            _Archive(20),
            {7: (3, 9)},
            {"records": [{"item_id": 17, "name": "Potion"}]},
        )

        self.assertEqual(set(references), {3, 9})
        self.assertEqual(references[3][0].quantity, 2)
        self.assertEqual(references[9][0].script_file_id, 7)

    def test_preserves_dedicated_and_multiple_common_script_callers(self) -> None:
        references = {0: (10435, 999), 1: (10435,)}
        engine = SimpleNamespace(
            parse_overworld_npcs=lambda data: tuple(
                SimpleNamespace(script_used=value) for value in references[data[0]]
            ),
            parse_overworld_furniture=lambda _data: (),
            resolve_common_script_member=resolve_common_script_member,
        )
        headers = (
            SimpleNamespace(header_id=0, overworld_file_id=1),
            SimpleNamespace(header_id=1, overworld_file_id=0),
        )

        owners = resolve_script_locations(
            engine,
            headers,
            (10, 11),
            _Archive(899),
            _Archive(2),
        )

        self.assertEqual(owners[10], (0,))
        self.assertEqual(owners[11], (1,))
        self.assertEqual(owners[877], (0, 1))
        self.assertNotIn(999, owners)

    def test_nested_trade_versions_flow_to_pokemon_acquisition(self) -> None:
        relationships = build_relationship_index(
            {
                "pokemon": {
                    "game": "black-white",
                    "records": [
                        {
                            "member": 548,
                            "national_dex_id": 548,
                            "name": "Petilil",
                            "slug": "petilil",
                            "public": True,
                        }
                    ],
                },
                "locations": {
                    "game": "black-white",
                    "records": [
                        {
                            "header_id": 23,
                            "name": "Nacrene City",
                            "npc_trades": [
                                {
                                    "offered_species_id": 548,
                                    "requested_species_name": "Cottonee",
                                    "versions": ["black"],
                                }
                            ],
                        }
                    ],
                },
            }
        )

        acquisition = relationships.pokemon_acquisition["petilil"]
        self.assertEqual(len(acquisition), 1)
        self.assertEqual(acquisition[0].versions, ("black",))

"""Trainer battle families for the retail Generation III games.

Rematches come from the ROM's rematch table, located by its pret source:
FireRed/LeafGreen's Vs. Seeker `sRematches` (six trainer IDs per row, the
first battle then one party per story tier; `0xFFFF` marks a tier that
keeps the previous party) and Emerald's Match Call `gRematchTable` (five
trainer IDs per row). A row whose slots all name the base trainer has no
distinct rematch party and is skipped.

Starter families come from the rival's scripts: each compares the
starter variable with every value and branches to one party's battle (see
`script_facts.find_starter_branches`). Each value is named for the species
it stands for, read from the ROM's starter scripts or table.

A profile names the contract its tables were verified under; it is never
inherited, so a hack is unresolved until it is verified on its own.
"""

from __future__ import annotations

import struct
from collections.abc import Mapping, Sequence
from typing import Any

from romwiki.schema.trainers import unverified_trainer_variants
from romwiki.util.errors import InvalidRomError, ProfileError

_CONTRACTS = {"frlg-retail-v1", "emerald-retail-v1"}
# Each row is padded to 16 bytes in both games.
REMATCH_ENTRY_SIZE = 16
_SKIP = 0xFFFF


def parse_rematch_table(
    data: bytes, *, count: int, trainers_per_entry: int
) -> tuple[tuple[int, ...], ...]:
    """Decode `count` rematch rows into their trainer IDs."""
    if len(data) != count * REMATCH_ENTRY_SIZE:
        raise InvalidRomError(
            f"Gen III rematch table has size {len(data)}, expected "
            f"{count * REMATCH_ENTRY_SIZE}"
        )
    return tuple(
        struct.unpack_from(f"<{trainers_per_entry}H", data, index * REMATCH_ENTRY_SIZE)
        for index in range(count)
    )


def resolve_trainer_variants(
    profile_id: str,
    parameters: Mapping[str, Any],
    records: Sequence[Mapping[str, Any]],
    *,
    selector_data: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    contract = parameters.get("trainer_variant_contract")
    if contract is None:
        return unverified_trainer_variants()
    if contract not in _CONTRACTS:
        raise ProfileError(
            f"Profile {profile_id!r} must select a verified Gen III trainer "
            "variant contract"
        )
    selectors = selector_data or {}
    rows = selectors.get("rematch_rows", ())
    label = selectors.get("rematch_label", "Rematch")
    starter_families = _starter_families(profile_id, records, selectors)
    return {
        "trainer_variant_support": {
            "starter_choice": {
                "status": "verified",
                "note": "Every starter comparison in the map scripts was followed "
                "to the battle its branch starts.",
            },
            "difficulty_mode": {"status": "unsupported"},
            "rematch_stage": {
                "status": "verified",
                "note": f"Every row of the ROM's {label} rematch table is enumerated.",
            },
            "story_stage": {"status": "unresolved"},
            "sibling_version": {"status": "unsupported"},
            "season": {"status": "unsupported"},
        },
        "battle_families": [
            *starter_families,
            *(
                {**family, "order": len(starter_families) + family["order"]}
                for family in _rematch_families(profile_id, records, rows, label)
            ),
        ],
    }


def _starter_families(
    profile_id: str,
    records: Sequence[Mapping[str, Any]],
    selectors: Mapping[str, Any],
) -> list[dict[str, Any]]:
    by_id = {record["trainer_id"]: record for record in records if record.get("party")}
    species = selectors.get("starter_species", {})
    names = selectors.get("species_names", ())
    families: list[dict[str, Any]] = []
    seen: set[tuple[tuple[int, int], ...]] = set()
    for map_name, branch in selectors.get("starter_branches", ()):
        choices = tuple(sorted(set(branch)))
        trainer_ids = [trainer_id for _, trainer_id in choices]
        if (
            choices in seen
            or len(set(trainer_ids)) != len(trainer_ids)
            or len(choices) < 2
            or not all(
                trainer_id in by_id and value in species
                for value, trainer_id in choices
            )
        ):
            continue
        seen.add(choices)
        families.append(
            {
                "id": f"starter-{trainer_ids[0]:04d}",
                "label": f"{map_name} rival battle",
                "order": len(families),
                "provenance": {
                    "source": "ROM event-script starter branch",
                    "reference": f"{profile_id}:starter-branch[{trainer_ids[0]}]",
                    "verification": (
                        "Each comparison against the starter variable was followed to "
                        "the literal battle command its branch starts."
                    ),
                },
                "variants": [
                    {
                        "trainer_id": trainer_id,
                        "order": order,
                        "conditions": [
                            {
                                "kind": "starter-choice",
                                "value": _slug(names[species[value]]),
                                "label": f"Player chose {names[species[value]]}",
                            }
                        ],
                    }
                    for order, (value, trainer_id) in enumerate(choices)
                ],
            }
        )
    return families


def _slug(name: str) -> str:
    return "-".join(name.lower().replace("é", "e").split())


def _rematch_families(
    profile_id: str,
    records: Sequence[Mapping[str, Any]],
    rows: Sequence[Sequence[int]],
    label: str,
) -> list[dict[str, Any]]:
    by_id = {record["trainer_id"]: record for record in records if record.get("party")}
    families: list[dict[str, Any]] = []
    for row in rows:
        base_id = row[0]
        base = by_id.get(base_id)
        if base is None:
            continue
        stages: list[tuple[int, int]] = []
        for slot, trainer_id in enumerate(row[1:], start=1):
            if (
                trainer_id not in (base_id, _SKIP, 0)
                and trainer_id in by_id
                and all(trainer_id != seen for _, seen in stages)
            ):
                stages.append((slot, trainer_id))
        if not stages:
            continue
        families.append(
            {
                "id": f"rematch-{base_id:04d}",
                "label": f"{base['class_name']} {base['name']} rematches".strip(),
                "order": len(families),
                "provenance": {
                    "source": f"ROM {label} rematch table",
                    "reference": f"{profile_id}:rematch-table[{base_id}]",
                    "verification": (
                        "The table was located by its pret source rows, and every "
                        "record it selects was enumerated from its stage slots."
                    ),
                },
                "variants": [
                    {
                        "trainer_id": base_id,
                        "order": 0,
                        "conditions": [
                            {
                                "kind": "rematch-stage",
                                "value": "initial",
                                "label": "First battle",
                            }
                        ],
                    },
                    *(
                        {
                            "trainer_id": trainer_id,
                            "order": order,
                            "conditions": [
                                {
                                    "kind": "rematch-stage",
                                    "value": f"rematch-{slot}",
                                    "label": f"{label} rematch {slot}",
                                }
                            ],
                        }
                        for order, (slot, trainer_id) in enumerate(stages, start=1)
                    ),
                ],
            }
        )
    return families

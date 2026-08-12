from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from romwiki.util.errors import ProfileError

_CONTRACTS = {"platinum-retail-v1", "renegade-platinum-v1.3.0"}


def _resolved_battle_location(
    records_by_id: Mapping[int, Mapping[str, Any]], trainer_ids: Sequence[int]
) -> str | None:
    """Return the map name every variant in a group resolves to, if they agree.

    Disagreement means the group does not describe one battle site, so the
    fallback label is used rather than picking one variant's map.
    """
    names = set()
    for trainer_id in trainer_ids:
        record = records_by_id.get(trainer_id)
        if record is None:
            return None
        places = record.get("script_references") or record.get("locations") or ()
        if not places:
            return None
        name = places[0].get("name")
        if not name:
            return None
        names.add(name)
    return names.pop() if len(names) == 1 else None


def _starter_branch_families(
    profile_id: str,
    records_by_id: Mapping[int, Mapping[str, Any]],
    available: set[Any],
    selector_data: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    """Build families from the decoded starter branches.

    Nothing here names a trainer, a battle site, or a starter: the engine reads
    which species each branch tests and which record it selects out of the
    profile's own scripts, so a hack that renumbers, relocates, or re-teams
    these battles is described from its own ROM.
    """
    decoded = (selector_data or {}).get("starter_branch_families") or ()
    species_names = (selector_data or {}).get("species_names") or ()
    families: list[dict[str, Any]] = []
    for family in decoded:
        trainer_ids = family.trainer_ids
        if not all(trainer_id in available for trainer_id in trainer_ids):
            continue
        location = _resolved_battle_location(records_by_id, trainer_ids)
        label = f"{location} rival battle" if location else "Rival battle"
        variants = []
        for order, (species_id, trainer_id) in enumerate(family.selected):
            species = _species_name(species_names, species_id)
            variants.append(
                {
                    "trainer_id": trainer_id,
                    "order": order,
                    "conditions": [
                        {
                            "kind": "starter-choice",
                            "value": species.lower(),
                            "label": f"Player chose {species}",
                        }
                    ],
                }
            )
        if family.fallthrough_trainer_id is not None:
            variants.append(
                {
                    "trainer_id": family.fallthrough_trainer_id,
                    "order": len(variants),
                    "conditions": [
                        {
                            "kind": "starter-choice",
                            "value": "remaining-starter",
                            "label": "Player chose the remaining starter",
                        }
                    ],
                }
            )
        if len(variants) < 2:
            continue
        families.append(
            {
                "id": f"starter-branch-{family.script_file_id:04d}",
                "label": label,
                "order": len(families),
                "provenance": {
                    "source": "ROM field-script starter branch",
                    "reference": f"{profile_id}:script-{family.script_file_id}",
                    "verification": (
                        "The script reads the player's starter species, and each "
                        "comparison against that variable was followed to the exact "
                        "trainer record its branch selects. Branch targets had to "
                        "land on a literal battle command, so no relationship is "
                        "inferred from names, adjacent IDs, levels, or party "
                        "similarity."
                    ),
                },
                "variants": variants,
            }
        )
    return families


def _species_name(species_names: Any, species_id: int) -> str:
    """Name a species from this profile's own name table, indexed or mapped."""
    if isinstance(species_names, Mapping):
        name = species_names.get(species_id)
    elif 0 <= species_id < len(species_names):
        name = species_names[species_id]
    else:
        name = None
    return name.title() if name else f"species-{species_id}"


def resolve_trainer_variants(
    profile_id: str,
    parameters: Mapping[str, Any],
    records: Sequence[Mapping[str, Any]],
    *,
    selector_data: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    contract = parameters.get("trainer_variant_contract")
    if contract not in _CONTRACTS:
        raise ProfileError(
            f"Profile {profile_id!r} must select a verified DPPT trainer variant contract"
        )
    available = {record.get("trainer_id") for record in records if record.get("party")}
    records_by_id = {
        record.get("trainer_id"): record for record in records if record.get("party")
    }
    families = _starter_branch_families(
        profile_id, records_by_id, available, selector_data
    )
    families.extend(
        _vs_seeker_families(
            profile_id, records, selector_data, first_order=len(families)
        )
    )
    return {
        "trainer_variant_support": {
            "starter_choice": {"status": "verified"},
            "difficulty_mode": {"status": "unsupported"},
            "rematch_stage": {
                "status": "partial",
                "note": (
                    "The Vs. Seeker rematch table is decoded and fully enumerated. "
                    "Gym Leader, Elite Four, and Battleground rematch records are "
                    "selected by logic that is not that table and remain unresolved."
                ),
            },
            "story_stage": {
                "status": "unresolved",
                "note": (
                    "Story staging exists — the rival is fought repeatedly — but no "
                    "selector for it has been decoded, and its surface is every "
                    "story-gated branch in every field script rather than one table. "
                    "It is deliberately not pursued, so no story stage is asserted."
                ),
            },
            "sibling_version": {"status": "unsupported"},
            "season": {"status": "unsupported"},
        },
        "battle_families": families,
    }


def _vs_seeker_families(
    profile_id: str,
    records: Sequence[Mapping[str, Any]],
    selector_data: Mapping[str, Any] | None,
    *,
    first_order: int,
) -> list[dict[str, Any]]:
    """Enumerate every chain the decoded Vs. Seeker table can select.

    Chains that only ever re-select their base trainer describe a rematch with
    an unchanged party, so they carry no variant information and are skipped.
    """
    chains = (selector_data or {}).get("rematch_chains")
    if not chains:
        return []

    by_id = {
        record.get("trainer_id"): record for record in records if record.get("party")
    }
    families: list[dict[str, Any]] = []
    for chain in chains:
        if not chain.has_distinct_records:
            continue
        base = by_id.get(chain.base_trainer_id)
        if base is None:
            continue
        # A slot re-selecting the base is the "unchanged party" encoding; only
        # slots holding a distinct, present record become variants.
        stages = [
            (slot, trainer_id)
            for slot, trainer_id in chain.stages
            if trainer_id != chain.base_trainer_id and trainer_id in by_id
        ]
        if not stages:
            continue
        order = first_order + len(families)
        families.append(
            {
                "id": f"vs-seeker-{chain.base_trainer_id:04d}",
                "label": f"{base['class_name']} {base['name']} Vs. Seeker rematches",
                "order": order,
                "provenance": {
                    "source": "ROM Vs. Seeker rematch table",
                    "reference": f"{profile_id}:rematch-table[{chain.base_trainer_id}]",
                    "verification": (
                        "The table was located by its own code references, and every "
                        "record it selects was enumerated from its exact stage slots."
                    ),
                },
                "variants": [
                    {
                        "trainer_id": chain.base_trainer_id,
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
                            "order": variant_order,
                            # The renderer derives its tab label from the value,
                            # so this carries the public Rematch axis. The slot
                            # is the ROM's story tier, not a running count, so
                            # a chain can legitimately skip numbers.
                            "conditions": [
                                {
                                    "kind": "rematch-stage",
                                    "value": f"rematch-{slot}",
                                    "label": f"Vs. Seeker rematch {slot}",
                                }
                            ],
                        }
                        for variant_order, (slot, trainer_id) in enumerate(
                            stages, start=1
                        )
                    ),
                ],
            }
        )
    return families

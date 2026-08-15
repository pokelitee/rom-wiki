from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from romwiki.util.errors import ProfileError

_CONTRACTS = {
    "hgss-retail-v1",
    "sacred-gold-storm-silver-v1.05",
}


def _species_name(species_names: Any, species_id: int) -> str:
    """Name a species from this profile's own name table, indexed or mapped."""
    if isinstance(species_names, Mapping):
        name = species_names.get(species_id)
    elif 0 <= species_id < len(species_names):
        name = species_names[species_id]
    else:
        name = None
    return name.title() if name else f"species-{species_id}"


def _resolved_battle_location(
    records_by_id: Mapping[int, Mapping[str, Any]], trainer_ids: Sequence[int]
) -> str | None:
    """The map every variant resolves to, if they agree."""
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
        if not all(t in records_by_id for t in family.trainer_ids):
            continue
        location = _resolved_battle_location(records_by_id, family.trainer_ids)
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
                "id": (f"starter-branch-{family.script_file_id:04d}-{family.position}"),
                "label": label,
                "order": len(families),
                "provenance": {
                    "source": "ROM field-script starter branch",
                    "reference": f"{profile_id}:script-{family.script_file_id}",
                    "verification": (
                        "The script compares the starter variable against each "
                        "starter species and jumps past the block it guards, so "
                        "every branch was followed to the exact trainer record it "
                        "selects. Branch targets had to land on a literal battle "
                        "command, so nothing is inferred from names, adjacent IDs, "
                        "levels, or party similarity."
                    ),
                },
                "variants": variants,
            }
        )
    return families


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
            f"Profile {profile_id!r} must select a verified HGSS trainer variant contract"
        )
    records_by_id = {
        record.get("trainer_id"): record for record in records if record.get("party")
    }
    families = _starter_branch_families(profile_id, records_by_id, selector_data)
    return {
        "trainer_variant_support": {
            "starter_choice": {"status": "verified"},
            "difficulty_mode": {"status": "unsupported"},
            "rematch_stage": {
                "status": "partial",
                "note": (
                    "Starter-selected Silver battles are verified. Phone-rematch "
                    "state tables are not decoded, so those records stay unrelated."
                ),
            },
            "story_stage": {
                "status": "partial",
                "note": (
                    "Starter-selected rival branches are decoded across the field "
                    "scripts. Other runtime-selected story stages stay unrelated "
                    "until their selector is decoded."
                ),
            },
            "sibling_version": {"status": "verified"},
            "season": {"status": "unsupported"},
        },
        "battle_families": families,
    }

"""Move-learner relationships: which Pokemon learn a given move, and how."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
from typing import Any

from ._shared import _record_variants, _record_versions


@dataclass(frozen=True, slots=True)
class MoveLearnerReference:
    move_id: int
    pokemon_id: int | str
    pokemon_name: str
    pokemon_slug: str
    pokemon_form: str | None
    method: str
    level: int | None
    machine_id: int | None
    machine_name: str | None
    machine_kind: str | None
    versions: tuple[str, ...]


def _move_learners(
    pokemon_records: list[dict[str, Any]],
) -> tuple[
    dict[int, list[MoveLearnerReference]],
    dict[int, list[MoveLearnerReference]],
]:
    level_up: dict[int, list[MoveLearnerReference]] = defaultdict(list)
    machines: dict[int, list[MoveLearnerReference]] = defaultdict(list)
    for pokemon in pokemon_records:
        if not pokemon.get("public", True) or not isinstance(pokemon.get("slug"), str):
            continue
        slug = pokemon["slug"]
        learner = {
            "pokemon_id": pokemon.get("member", slug),
            "pokemon_name": str(pokemon.get("name", slug)),
            "pokemon_slug": slug,
            "pokemon_form": pokemon.get("form"),
        }
        # A sibling version may teach a different set (FireRed and LeafGreen
        # each give Deoxys its own learnset); a move learned the same way in
        # several versions is one reference listing all of them.
        learned: dict[MoveLearnerReference, set[str]] = {}
        for versions, variant in _record_variants(pokemon):
            for entry in variant.get("level_up_moves", []):
                move = entry.get("move")
                if not isinstance(move, dict) or not isinstance(move.get("id"), int):
                    continue
                reference = MoveLearnerReference(
                    move_id=move["id"],
                    **learner,
                    method="level-up",
                    level=entry.get("level"),
                    machine_id=None,
                    machine_name=None,
                    machine_kind=None,
                    versions=(),
                )
                learned.setdefault(reference, set()).update(versions)
            for machine in variant.get("machines", []):
                move = machine.get("move")
                if not isinstance(move, dict) or not isinstance(move.get("id"), int):
                    continue
                reference = MoveLearnerReference(
                    move_id=move["id"],
                    **learner,
                    method="machine",
                    level=None,
                    machine_id=machine.get("id"),
                    machine_name=machine.get("name"),
                    machine_kind=machine.get("kind"),
                    versions=(),
                )
                learned.setdefault(reference, set()).update(versions)
        order = _record_versions(pokemon)
        for reference, learned_in in learned.items():
            target = level_up if reference.method == "level-up" else machines
            target[reference.move_id].append(
                replace(
                    reference,
                    versions=tuple(
                        version for version in order if version in learned_in
                    ),
                )
            )
    return level_up, machines


def _learner_sort_key(value: MoveLearnerReference) -> tuple[Any, ...]:
    return (
        value.pokemon_slug,
        value.level if value.level is not None else -1,
        value.machine_id if value.machine_id is not None else -1,
        value.versions,
    )

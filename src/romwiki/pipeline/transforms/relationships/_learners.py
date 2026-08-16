"""Move-learner relationships: which Pokemon learn a given move, and how."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from ._shared import _record_versions


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
        versions = _record_versions(pokemon)
        slug = pokemon["slug"]
        pokemon_id = pokemon.get("member", slug)
        pokemon_name = str(pokemon.get("name", slug))
        pokemon_form = pokemon.get("form")
        for entry in pokemon.get("level_up_moves", []):
            move = entry.get("move")
            if not isinstance(move, dict) or not isinstance(move.get("id"), int):
                continue
            level_up[move["id"]].append(
                MoveLearnerReference(
                    move_id=move["id"],
                    pokemon_id=pokemon_id,
                    pokemon_name=pokemon_name,
                    pokemon_slug=slug,
                    pokemon_form=pokemon_form,
                    method="level-up",
                    level=entry.get("level"),
                    machine_id=None,
                    machine_name=None,
                    machine_kind=None,
                    versions=versions,
                )
            )
        for machine in pokemon.get("machines", []):
            move = machine.get("move")
            if not isinstance(move, dict) or not isinstance(move.get("id"), int):
                continue
            machines[move["id"]].append(
                MoveLearnerReference(
                    move_id=move["id"],
                    pokemon_id=pokemon_id,
                    pokemon_name=pokemon_name,
                    pokemon_slug=slug,
                    pokemon_form=pokemon_form,
                    method="machine",
                    level=None,
                    machine_id=machine.get("id"),
                    machine_name=machine.get("name"),
                    machine_kind=machine.get("kind"),
                    versions=versions,
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

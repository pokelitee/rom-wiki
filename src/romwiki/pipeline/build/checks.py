"""Content checks that every game's datasets must pass before publication.

Envelope validation only proves a dataset is well formed. These checks catch
extraction mistakes that still produce well-formed data, such as a species
table read with the wrong identity mapping or bounds. Each check holds for
every correctly extracted retail game and hack, so a failure is a decoding
problem to fix, never a value to tolerate.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Hashable, Iterable, Mapping
from typing import Any

from romwiki.util.errors import DataSourceError

# Highest base stat any Pokémon can store: the personal records use one byte.
_MAX_BASE_STAT = 255
_RECORD_IDS = {
    "abilities": "ability_id",
    "items": "item_id",
    "moves": "move_id",
    "trainers": "trainer_id",
}


def check_game_datasets(game: str, datasets: Mapping[str, Mapping[str, Any]]) -> None:
    """Raise `DataSourceError` listing every content problem in `datasets`.

    `datasets` maps dataset kinds to enriched datasets. Kinds that are absent,
    as in a focused section build, are skipped along with the cross-dataset
    references that need them.
    """
    problems = find_dataset_problems(datasets)
    if problems:
        listed = "\n".join(f"- {problem}" for problem in problems)
        raise DataSourceError(f"{game} datasets failed content checks:\n{listed}")


def find_dataset_problems(datasets: Mapping[str, Mapping[str, Any]]) -> list[str]:
    problems: list[str] = []
    pokemon = datasets.get("pokemon")
    if pokemon is not None:
        problems.extend(_pokemon_problems(pokemon))
    for kind, key in _RECORD_IDS.items():
        dataset = datasets.get(kind)
        if dataset is not None:
            problems.extend(_identity_problems(kind, dataset["records"], key))
    if pokemon is not None:
        problems.extend(_reference_problems(pokemon, datasets))
    return problems


def _pokemon_problems(dataset: Mapping[str, Any]) -> list[str]:
    public = [record for record in dataset["records"] if record.get("public")]
    problems = []
    if duplicated := _duplicates(record.get("slug") for record in public):
        problems.append(f"pokemon: duplicate slugs {_sample(duplicated)}")
    if duplicated := _duplicates(
        (record.get("national_dex_id"), record.get("form")) for record in public
    ):
        problems.append(
            f"pokemon: duplicate National Dex numbers and forms {_sample(duplicated)}"
        )
    if missing := [record.get("slug") for record in public if not record.get("name")]:
        problems.append(f"pokemon: missing names {_sample(missing)}")
    if undexed := [
        record.get("slug")
        for record in public
        if not isinstance(record.get("national_dex_id"), int)
    ]:
        problems.append(f"pokemon: missing National Dex numbers {_sample(undexed)}")
    numbers = {
        record["national_dex_id"]
        for record in public
        if isinstance(record.get("national_dex_id"), int)
    }
    if numbers and (gaps := sorted(set(range(1, max(numbers) + 1)) - numbers)):
        problems.append(f"pokemon: National Dex numbers missing {_sample(gaps)}")
    if out_of_range := [
        record.get("slug")
        for record in public
        if not all(
            isinstance(value, int) and 1 <= value <= _MAX_BASE_STAT
            for value in record.get("base_stats", {}).values()
        )
        or not record.get("base_stats")
    ]:
        problems.append(f"pokemon: base stats out of range {_sample(out_of_range)}")
    # Only engines that extract learnsets record this source; without it an
    # empty move list is expected rather than a decoding failure.
    if "level_up_learnsets" in dataset.get("supplemental_sources", {}) and (
        moveless := [
            record.get("slug") for record in public if not record.get("level_up_moves")
        ]
    ):
        problems.append(f"pokemon: no level-up moves {_sample(moveless)}")
    return problems


def _identity_problems(
    kind: str, records: Iterable[Mapping[str, Any]], key: str
) -> list[str]:
    records = list(records)
    problems = []
    if duplicated := _duplicates(record.get(key) for record in records):
        problems.append(f"{kind}: duplicate {key} values {_sample(duplicated)}")
    if duplicated := _duplicates(
        record["slug"] for record in records if record.get("slug")
    ):
        problems.append(f"{kind}: duplicate slugs {_sample(duplicated)}")
    return problems


def _reference_problems(
    pokemon: Mapping[str, Any], datasets: Mapping[str, Mapping[str, Any]]
) -> list[str]:
    problems = []
    records = pokemon["records"]
    public = [record for record in records if record.get("public")]
    slugs = {record.get("slug") for record in records}
    if missing := {
        evolution["target"].get("slug")
        for record in public
        for evolution in record.get("evolutions") or []
        if evolution.get("target") and evolution["target"].get("slug") not in slugs
    }:
        problems.append(f"pokemon: evolution targets not found {_sample(missing)}")
    moves = datasets.get("moves")
    if moves is not None:
        move_ids = {record.get("move_id") for record in moves["records"]}
        if missing := {
            learned["move"].get("id")
            for record in public
            for learned in record.get("level_up_moves") or []
            if learned["move"].get("id") not in move_ids
        }:
            problems.append(f"pokemon: level-up moves not found {_sample(missing)}")
    trainers = datasets.get("trainers")
    if trainers is not None and (
        missing := {
            member["pokemon"].get("slug")
            for trainer in trainers["records"]
            for member in trainer.get("party") or []
            if member.get("pokemon") and member["pokemon"].get("slug") not in slugs
        }
    ):
        problems.append(f"trainers: party Pokémon not found {_sample(missing)}")
    return problems


def _duplicates(values: Iterable[Hashable]) -> list[Any]:
    return [value for value, count in Counter(values).items() if count > 1]


def _sample(values: Iterable[Any], limit: int = 5) -> str:
    ordered = sorted(values, key=repr)
    shown = ", ".join(str(value) for value in ordered[:limit])
    more = len(ordered) - limit
    return f"({len(ordered)}): {shown}" + (f", and {more} more" if more > 0 else "")

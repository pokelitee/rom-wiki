from __future__ import annotations

import struct

import pytest

from romwiki.engines.gen3.shared.battle_variants import (
    parse_rematch_table,
    resolve_trainer_variants,
)
from romwiki.schema.trainers import validate_trainer_battle_families
from romwiki.util.errors import ProfileError

_CONTRACT = {"trainer_variant_contract": "frlg-retail-v1"}


def _trainer(trainer_id: int) -> dict[str, object]:
    return {
        "trainer_id": trainer_id,
        "class_name": "Youngster",
        "name": "Ben",
        "party": [{"level": 10 + trainer_id}],
    }


def test_without_a_contract_every_mechanic_is_unresolved() -> None:
    result = resolve_trainer_variants("firered-omega", {}, [_trainer(1)])

    assert result["battle_families"] == []
    assert {m["status"] for m in result["trainer_variant_support"].values()} == {
        "unresolved"
    }


def test_rejects_an_unknown_contract() -> None:
    with pytest.raises(ProfileError):
        resolve_trainer_variants(
            "firered-us", {"trainer_variant_contract": "typo"}, [_trainer(1)]
        )


def test_rematch_rows_become_families_by_tier() -> None:
    records = [_trainer(trainer_id) for trainer_id in (1, 2, 3, 4)]
    rows = (
        # Base 1; tier 2 keeps the previous party (0xFFFF); tier 4 repeats 3.
        (1, 2, 0xFFFF, 3, 3, 0),
        # Every slot is the base: no rematch party.
        (4, 4, 4, 4, 4, 4),
    )

    result = resolve_trainer_variants(
        "firered-us",
        _CONTRACT,
        records,
        selector_data={"rematch_rows": rows, "rematch_label": "Vs. Seeker"},
    )

    (family,) = result["battle_families"]
    assert [
        (variant["trainer_id"], variant["conditions"][0]["label"])
        for variant in family["variants"]
    ] == [
        (1, "First battle"),
        (2, "Vs. Seeker rematch 1"),
        (3, "Vs. Seeker rematch 3"),
    ]
    validate_trainer_battle_families(
        result["battle_families"], result["trainer_variant_support"], [1, 2, 3, 4]
    )


def test_parses_rows_padded_to_sixteen_bytes() -> None:
    data = struct.pack("<8H", 37, 40, 41, 42, 43, 0, 33, 0) * 2

    rows = parse_rematch_table(data, count=2, trainers_per_entry=5)

    assert rows == ((37, 40, 41, 42, 43), (37, 40, 41, 42, 43))


def test_starter_branches_become_one_family_per_battle() -> None:
    records = [_trainer(trainer_id) for trainer_id in (426, 427, 428)]
    branch = ((0, 428), (1, 427), (2, 426))
    selectors = {
        "starter_branches": [("Pallet Town", branch), ("Pallet Town", branch)],
        "starter_species": {0: 1, 1: 7, 2: 4},
        "species_names": [
            "?",
            "Bulbasaur",
            "?",
            "?",
            "Charmander",
            "?",
            "?",
            "Squirtle",
        ],
    }

    result = resolve_trainer_variants(
        "firered-us", _CONTRACT, records, selector_data=selectors
    )

    (family,) = result["battle_families"]
    assert family["label"] == "Pallet Town rival battle"
    assert [
        (variant["trainer_id"], variant["conditions"][0]["value"])
        for variant in family["variants"]
    ] == [(428, "bulbasaur"), (427, "squirtle"), (426, "charmander")]
    validate_trainer_battle_families(
        result["battle_families"], result["trainer_variant_support"], [426, 427, 428]
    )

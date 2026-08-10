from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction
from types import MappingProxyType
from typing import Any

from romwiki.profiles.models import GameProfile
from romwiki.schema.versions import TYPE_CHART_SCHEMA_VERSION
from romwiki.util.errors import DataSourceError, ProfileError

_MULTIPLIERS = {
    "0": Fraction(0),
    "1/4": Fraction(1, 4),
    "1/2": Fraction(1, 2),
    "1": Fraction(1),
    "2": Fraction(2),
    "4": Fraction(4),
}
_TYPE_NAMES = (
    "normal",
    "fighting",
    "flying",
    "poison",
    "ground",
    "rock",
    "bug",
    "ghost",
    "steel",
    "fire",
    "water",
    "grass",
    "electric",
    "psychic",
    "ice",
    "dragon",
    "dark",
)


@dataclass(frozen=True, slots=True)
class TypeChartFamily:
    id: str
    types: tuple[str, ...]
    matrix: Mapping[tuple[str, str], str]


@dataclass(frozen=True, slots=True)
class RegisteredTypeChart:
    id: str
    family: TypeChartFamily

    @property
    def types(self) -> tuple[str, ...]:
        return self.family.types

    @property
    def matrix(self) -> Mapping[tuple[str, str], str]:
        return self.family.matrix


def _canonical_matrix() -> dict[tuple[str, str], str]:
    matrix = {
        (attacking, defending): "1"
        for attacking in _TYPE_NAMES
        for defending in _TYPE_NAMES
    }
    rules = {
        "normal": ({}, {"rock", "steel"}, {"ghost"}),
        "fighting": (
            {"normal", "ice", "rock", "dark", "steel"},
            {"poison", "flying", "psychic", "bug"},
            {"ghost"},
        ),
        "flying": ({"fighting", "bug", "grass"}, {"rock", "steel", "electric"}, set()),
        "poison": ({"grass"}, {"poison", "ground", "rock", "ghost"}, {"steel"}),
        "ground": (
            {"poison", "rock", "steel", "fire", "electric"},
            {"bug", "grass"},
            {"flying"},
        ),
        "rock": (
            {"flying", "bug", "fire", "ice"},
            {"fighting", "ground", "steel"},
            set(),
        ),
        "bug": (
            {"grass", "psychic", "dark"},
            {"fighting", "flying", "poison", "ghost", "steel", "fire"},
            set(),
        ),
        "ghost": ({"ghost", "psychic"}, {"dark", "steel"}, {"normal"}),
        "steel": ({"rock", "ice"}, {"steel", "fire", "water", "electric"}, set()),
        "fire": (
            {"bug", "steel", "grass", "ice"},
            {"rock", "fire", "water", "dragon"},
            set(),
        ),
        "water": ({"ground", "rock", "fire"}, {"water", "grass", "dragon"}, set()),
        "grass": (
            {"ground", "rock", "water"},
            {"flying", "poison", "bug", "steel", "fire", "grass", "dragon"},
            set(),
        ),
        "electric": ({"flying", "water"}, {"grass", "electric", "dragon"}, {"ground"}),
        "psychic": ({"fighting", "poison"}, {"steel", "psychic"}, {"dark"}),
        "ice": (
            {"flying", "ground", "grass", "dragon"},
            {"steel", "fire", "water", "ice"},
            set(),
        ),
        "dragon": ({"dragon"}, {"steel"}, set()),
        "dark": ({"ghost", "psychic"}, {"fighting", "dark", "steel"}, set()),
    }
    for attacking, (strong, resisted, immune) in rules.items():
        for defending in strong:
            matrix[attacking, defending] = "2"
        for defending in resisted:
            matrix[attacking, defending] = "1/2"
        for defending in immune:
            matrix[attacking, defending] = "0"
    return matrix


TYPE_CHART_FAMILIES = {
    "gen2-5": TypeChartFamily(
        "gen2-5",
        _TYPE_NAMES,
        MappingProxyType(_canonical_matrix()),
    ),
}
TYPE_CHARTS = {
    "gen2-5": RegisteredTypeChart("gen2-5", TYPE_CHART_FAMILIES["gen2-5"]),
    # Backward-compatible profile aliases. Chart selection describes battle
    # mechanics, not which extraction engine happens to consume them.
    "gen4": RegisteredTypeChart("gen4", TYPE_CHART_FAMILIES["gen2-5"]),
    "gen5": RegisteredTypeChart("gen5", TYPE_CHART_FAMILIES["gen2-5"]),
}


def build_type_dataset(
    profile: GameProfile,
    *,
    game: str | None = None,
) -> dict[str, Any]:
    config = profile.type_chart
    if config is None:
        raise ProfileError(f"Profile {profile.id} does not declare a type chart")
    try:
        registered = TYPE_CHARTS[config.chart]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} selects unknown type chart {config.chart!r}"
        ) from error
    validate_type_chart(registered)
    types = (*registered.types, *config.additional_types)
    if len(set(types)) != len(types):
        raise ProfileError(f"Profile {profile.id} declares a duplicate type")
    matrix = {
        (attacking, defending): (
            registered.matrix.get((attacking, defending), "1")
            if attacking in registered.types and defending in registered.types
            else "1"
        )
        for attacking in types
        for defending in types
    }
    for key, multiplier in config.overrides.items():
        match = re.fullmatch(r"([a-z0-9-]+)>([a-z0-9-]+)", key)
        if match is None:
            raise ProfileError(f"Invalid type chart matchup {key!r}")
        attacking, defending = match.groups()
        if attacking not in types or defending not in types:
            raise ProfileError(f"Unknown type in chart matchup {key!r}")
        if multiplier not in _MULTIPLIERS:
            raise ProfileError(
                f"Invalid multiplier {multiplier!r} for chart matchup {key!r}"
            )
        matrix[attacking, defending] = multiplier
    return {
        "schema_version": TYPE_CHART_SCHEMA_VERSION,
        "dataset": "types",
        "kind": "types",
        "game": game or profile.id,
        "engine": profile.engine,
        "chart": config.chart,
        "chart_family": registered.family.id,
        "source_kind": (
            "profile-override"
            if config.additional_types or config.overrides
            else "engine-canonical"
        ),
        "provenance": {
            "profile": profile.id,
            "engine": profile.engine,
            "chart": config.chart,
            "chart_family": registered.family.id,
            "additional_types": list(config.additional_types),
            "overrides": dict(sorted(config.overrides.items())),
        },
        "record_count": len(types),
        "records": [
            {
                "id": index,
                "name": attacking,
                "matchups": [
                    {
                        "defending_type": defending,
                        "multiplier": matrix[attacking, defending],
                    }
                    for defending in types
                ],
            }
            for index, attacking in enumerate(types)
        ],
    }


def validate_type_chart(chart: RegisteredTypeChart) -> None:
    if not chart.types or len(set(chart.types)) != len(chart.types):
        raise DataSourceError("Type charts require unique type names")
    expected = {
        (attacking, defending) for attacking in chart.types for defending in chart.types
    }
    actual = set(chart.matrix)
    if actual != expected:
        missing = expected - actual
        detail = "missing" if missing else "unknown"
        raise DataSourceError(f"Type chart has {detail} matchup entries")
    if any(multiplier not in _MULTIPLIERS for multiplier in chart.matrix.values()):
        raise DataSourceError("Type chart has an invalid multiplier")


def defensive_effectiveness(
    dataset: dict[str, Any],
    defending_types: tuple[str, ...],
) -> dict[str, tuple[str, ...]]:
    matrix = {
        (record["name"], matchup["defending_type"]): matchup["multiplier"]
        for record in dataset["records"]
        for matchup in record["matchups"]
    }
    attacking_types = tuple(record["name"] for record in dataset["records"])
    unknown = set(defending_types) - set(attacking_types)
    if unknown:
        raise DataSourceError(
            f"Unknown defending type(s): {', '.join(sorted(unknown))}"
        )
    grouped: dict[str, list[str]] = {}
    for attacking in attacking_types:
        multiplier = Fraction(1)
        for defending in defending_types:
            multiplier *= _MULTIPLIERS[matrix[attacking, defending]]
        label = _fraction_label(multiplier)
        grouped.setdefault(label, []).append(attacking)
    return {label: tuple(names) for label, names in grouped.items()}


def _fraction_label(value: Fraction) -> str:
    for label, multiplier in _MULTIPLIERS.items():
        if value == multiplier:
            return label
    raise DataSourceError(f"Unsupported combined type multiplier: {value}")

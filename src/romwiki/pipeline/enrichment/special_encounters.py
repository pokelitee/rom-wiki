from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class SpecialEncounterGroup:
    key: str
    label: str
    method: str
    condition: str
    slots: tuple[Mapping[str, Any], ...]
    slotted: bool


_DIRECT_GROUPS = (
    ("land_swarm", "Land swarm", "Walking", "land swarm"),
    ("surf_swarm", "Surf swarm", "Surf", "surf swarm"),
    ("hoenn_radio", "Hoenn Sound radio", "Walking", "Hoenn Sound radio"),
    ("sinnoh_radio", "Sinnoh Sound radio", "Walking", "Sinnoh Sound radio"),
    ("night_fishing", "Night fishing", "Fishing", "night fishing"),
    ("fishing_swarm", "Fishing swarm", "Fishing", "fishing swarm"),
)


def special_encounter_groups(
    special: Mapping[str, Any] | None,
) -> tuple[SpecialEncounterGroup, ...]:
    """Expose conditional encounters through semantic groups.

    The serialized input shapes remain unchanged. Consumers use method and
    condition semantics instead of branching on an engine-family marker.
    """
    if not special:
        return ()
    if any(key in special for key, *_ in _DIRECT_GROUPS):
        return _direct_groups(special)
    return _slotted_groups(special)


def _direct_groups(special: Mapping[str, Any]) -> tuple[SpecialEncounterGroup, ...]:
    groups = []
    for key, label, method, condition in _DIRECT_GROUPS:
        value = special.get(key)
        values = value if isinstance(value, list) else [value]
        slots = tuple(
            {"pokemon": pokemon, "species_id": pokemon.get("id")}
            for pokemon in values
            if isinstance(pokemon, Mapping)
        )
        if slots:
            groups.append(
                SpecialEncounterGroup(
                    key=key,
                    label=label,
                    method=method,
                    condition=condition,
                    slots=slots,
                    slotted=False,
                )
            )
    return tuple(groups)


def _slotted_groups(
    special: Mapping[str, Any],
) -> tuple[SpecialEncounterGroup, ...]:
    groups: list[SpecialEncounterGroup] = []
    for key, label in (
        ("swarm", "Swarm"),
        ("day", "Day replacements"),
        ("night", "Night replacements"),
    ):
        _append_slotted_group(groups, key, label, key, special.get(key))
    dual_slot = special.get("dual_slot")
    if isinstance(dual_slot, Mapping):
        for game, slots in dual_slot.items():
            game_name = str(game)
            _append_slotted_group(
                groups,
                f"dual_slot:{game_name}",
                f"Dual-slot: {game_name.replace('-', ' ').title()}",
                f"dual-slot: {game_name}",
                slots,
            )
    radar = special.get("radar")
    if isinstance(radar, list):
        slots = tuple(
            {"pokemon": pokemon, "species_id": pokemon.get("id")}
            for pokemon in radar
            if isinstance(pokemon, Mapping)
        )
        if slots:
            groups.append(
                SpecialEncounterGroup(
                    key="radar",
                    label="Poké Radar",
                    method="Walking",
                    condition="Poké Radar",
                    slots=slots,
                    slotted=False,
                )
            )
    return tuple(groups)


def _append_slotted_group(
    groups: list[SpecialEncounterGroup],
    key: str,
    label: str,
    condition: str,
    values: Any,
) -> None:
    if not isinstance(values, list):
        return
    slots = tuple(
        slot
        for slot in values
        if isinstance(slot, Mapping) and isinstance(slot.get("pokemon"), Mapping)
    )
    if slots:
        groups.append(
            SpecialEncounterGroup(
                key=key,
                label=label,
                method="Walking",
                condition=condition,
                slots=slots,
                slotted=True,
            )
        )

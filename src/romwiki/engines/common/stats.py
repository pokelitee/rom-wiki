"""Battle-stat arithmetic shared by Generations III through V.

These are the games' own integer formulas, so every division floors.
"""

from __future__ import annotations

STAT_NAMES = ("hp", "attack", "defense", "special_attack", "special_defense", "speed")

#: Shedinja's National Dex ID. Its maximum HP is always 1, whatever the inputs.
SHEDINJA_SPECIES_ID = 292

_NATURE_INCREASE_PERCENT = 110
_NATURE_DECREASE_PERCENT = 90


def hp_stat(*, species_id: int, base: int, iv: int, ev: int, level: int) -> int:
    if species_id == SHEDINJA_SPECIES_ID:
        return 1
    return ((2 * base + iv + ev // 4) * level) // 100 + level + 10


def neutral_stat(*, base: int, iv: int, ev: int, level: int) -> int:
    """A non-HP stat before its nature multiplier is applied."""
    return ((2 * base + iv + ev // 4) * level) // 100 + 5


def nature_increased_stat(neutral: int) -> int:
    return neutral * _NATURE_INCREASE_PERCENT // 100


def nature_decreased_stat(neutral: int) -> int:
    return neutral * _NATURE_DECREASE_PERCENT // 100

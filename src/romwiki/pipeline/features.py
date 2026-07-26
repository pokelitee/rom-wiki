from __future__ import annotations

from typing import Any

from romwiki.engines.registry import get_engine
from romwiki.profiles.models import GameProfile

EGG_MOVES = "egg-moves"
MOVE_TUTORS = "move-tutors"
CONTESTS = "contests"
POST_BATTLE_HEALING = "post-battle-healing"
VICTORY_ITEMS = "victory-items"


def effective_features(profile: GameProfile) -> tuple[str, ...]:
    """Return normalized presentation features supported by this exact profile."""
    features = set(get_engine(profile.engine).presentation_features)
    if "egg_moves" in profile.layout or "egg_move_offset" in profile.parameters:
        features.add(EGG_MOVES)
    if "tutor_move_offset" in profile.parameters:
        features.add(MOVE_TUTORS)
    return tuple(sorted(features))


def attach_features(dataset: dict[str, Any], profile: GameProfile) -> dict[str, Any]:
    return {**dataset, "features": list(effective_features(profile))}

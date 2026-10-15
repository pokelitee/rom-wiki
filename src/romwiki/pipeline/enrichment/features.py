from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from romwiki.engines.registry import get_engine
from romwiki.profiles.models import GameProfile

EGG_MOVES = "egg-moves"
MOVE_TUTORS = "move-tutors"
CONTESTS = "contests"


def effective_features(profile: GameProfile) -> tuple[str, ...]:
    """Return normalized presentation features supported by this exact profile."""
    features = set(get_engine(profile.engine).presentation_features)
    if "egg_moves" in profile.layout or "egg_move_offset" in profile.parameters:
        features.add(EGG_MOVES)
    if "tutor_move_offset" in profile.parameters:
        features.add(MOVE_TUTORS)
    return tuple(sorted(features))


def attach_features[DatasetT: Mapping[str, Any]](
    dataset: DatasetT, profile: GameProfile
) -> DatasetT:
    return cast(DatasetT, {**dataset, "features": list(effective_features(profile))})

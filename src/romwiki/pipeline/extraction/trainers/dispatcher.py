from __future__ import annotations

from typing import Any

from romwiki.engines.registry import get_engine
from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.util.errors import DataSourceError, ProfileError


def extract_trainer_dataset(result: InspectionResult) -> dict[str, Any]:
    if result.match is None:
        raise ProfileError("A known game profile is required for trainer extraction")
    profile = result.match.profile
    trainer_format = get_engine(profile.engine).formats.trainers
    if trainer_format == "battle-mode":
        from romwiki.pipeline.extraction.trainers.battle_mode import (
            extract_battle_mode_trainer_dataset,
        )

        return extract_battle_mode_trainer_dataset(result)
    if trainer_format == "pointer-party":
        from romwiki.pipeline.extraction.trainers.pointer_party import (
            extract_pointer_party_trainer_dataset,
        )

        return extract_pointer_party_trainer_dataset(result)
    if trainer_format != "class-gender":
        raise DataSourceError(f"Unsupported trainer format: {trainer_format!r}")
    from romwiki.pipeline.extraction.trainers.class_gender import (
        extract_class_gender_trainer_dataset,
    )

    return extract_class_gender_trainer_dataset(result)

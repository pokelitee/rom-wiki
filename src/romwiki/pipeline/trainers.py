from __future__ import annotations

from pathlib import Path
from typing import Any

from romwiki.engines.registry import get_engine
from romwiki.pipeline.identify import InspectionResult
from romwiki.util.errors import DataSourceError, ProfileError
from romwiki.util.json_io import write_json_atomic


def extract_trainer_dataset(result: InspectionResult) -> dict[str, Any]:
    if result.match is None:
        raise ProfileError("A known game profile is required for trainer extraction")
    profile = result.match.profile
    trainer_format = get_engine(profile.engine).formats.trainers
    if trainer_format == "battle-mode":
        from romwiki.pipeline.trainer_battle_mode import (
            extract_battle_mode_trainer_dataset,
        )

        return extract_battle_mode_trainer_dataset(result)
    if trainer_format != "class-gender":
        raise DataSourceError(f"Unsupported trainer format: {trainer_format!r}")
    from romwiki.pipeline.trainer_class_gender import (
        extract_class_gender_trainer_dataset,
    )

    return extract_class_gender_trainer_dataset(result)


def write_trainer_dataset(dataset: dict[str, Any], output_path: Path) -> None:
    write_json_atomic(output_path, dataset)

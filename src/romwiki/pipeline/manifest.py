from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from romwiki import __version__
from romwiki.pipeline.identify import InspectionResult


def create_manifest(result: InspectionResult) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "generator": {"name": "rom-wiki", "version": __version__},
        "input": result.to_dict(),
        "datasets": {},
    }


def write_manifest(manifest: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(f"{output_path.suffix}.tmp")
    temporary_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(output_path)


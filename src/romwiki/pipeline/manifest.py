from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from romwiki import __version__
from romwiki.pipeline.identify import InspectionResult
from romwiki.schema.versions import MANIFEST_SCHEMA_VERSION
from romwiki.util.json_io import write_json_atomic


def create_manifest(result: InspectionResult) -> dict[str, Any]:
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "generator": {"name": "rom-wiki", "version": __version__},
        "input": result.to_dict(),
        "datasets": {},
    }


def write_manifest(manifest: dict[str, Any], output_path: Path) -> None:
    write_json_atomic(output_path, manifest)


from __future__ import annotations

from pathlib import Path
from typing import Any

from romwiki.util.json_io import write_json_atomic


def write_dataset(
    dataset: dict[str, Any], output_path: Path, *, compact: bool = False
) -> None:
    write_json_atomic(output_path, dataset, compact=compact)

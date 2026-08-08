from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


@lru_cache(maxsize=1)
def extraction_source_fingerprint() -> str:
    """Hash code that can change normalized raw extraction output."""
    package_root = Path(__file__).resolve().parents[1]
    digest = hashlib.sha256()
    for directory_name in ("engines", "pipeline", "platforms", "profiles", "schema"):
        directory = package_root / directory_name
        for path in sorted(directory.rglob("*.py")):
            digest.update(path.relative_to(package_root).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
    return digest.hexdigest()


def profile_fingerprint(profile: Any) -> str:
    """Hash the resolved profile values that control extraction."""
    value = asdict(profile) if is_dataclass(profile) else {"id": profile.id}
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

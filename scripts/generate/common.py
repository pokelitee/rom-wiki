"""Paths shared by the generators in this directory."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
GAMES_CONFIG = ROOT / ".local" / "games.toml"


def local_config() -> dict[str, Any]:
    """`.local/games.toml`, the registry of local ROMs and PokéDB."""
    try:
        return tomllib.loads(GAMES_CONFIG.read_text(encoding="utf-8"))
    except OSError as error:
        raise SystemExit(f"This generator needs {GAMES_CONFIG} ({error})") from error


def local_path(value: str) -> Path:
    """A path from the local registry, which is relative to the registry."""
    return (GAMES_CONFIG.parent / value).resolve()


def check_or_write(outputs: dict[Path, str], *, check: bool) -> None:
    """Write each generated file, or with `check` fail if any is stale."""
    if check:
        stale = [
            path
            for path, text in outputs.items()
            if not path.is_file() or path.read_text(encoding="utf-8") != text
        ]
        if stale:
            names = ", ".join(str(path.relative_to(ROOT)) for path in stale)
            raise SystemExit(f"Out of date: {names}; rerun the generator")
        return
    for path, text in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib

from romwiki.util.errors import LocalConfigError


@dataclass(frozen=True, slots=True)
class LocalGamePaths:
    game_id: str
    patched_rom: Path
    base_rom: Path | None

    def rom(self, *, base: bool = False) -> Path:
        path = self.base_rom if base else self.patched_rom
        label = "base" if base else "patched"
        if path is None:
            raise LocalConfigError(
                f"Game {self.game_id} does not define a {label}_rom path"
            )
        if not path.is_file():
            raise LocalConfigError(
                f"Configured {label} ROM does not exist for {self.game_id}: {path}"
            )
        return path


class LocalGameRegistry:
    def __init__(self, games: dict[str, LocalGamePaths]) -> None:
        self.games = dict(games)

    @classmethod
    def load(cls, path: Path) -> LocalGameRegistry:
        resolved = path.resolve()
        if not resolved.is_file():
            raise LocalConfigError(f"Local game configuration does not exist: {resolved}")
        try:
            with resolved.open("rb") as stream:
                data = tomllib.load(stream)
        except tomllib.TOMLDecodeError as error:
            raise LocalConfigError(
                f"Invalid local game configuration {resolved}: {error}"
            ) from error

        if data.get("version", 1) != 1:
            raise LocalConfigError(
                f"Unsupported local game configuration version in {resolved}"
            )
        raw_games = data.get("games")
        if not isinstance(raw_games, dict) or not raw_games:
            raise LocalConfigError(
                f"Local game configuration contains no game entries: {resolved}"
            )

        games = {
            game_id: _load_game_paths(game_id, value, resolved.parent, resolved)
            for game_id, value in raw_games.items()
        }
        return cls(games)

    def get(self, game_id: str) -> LocalGamePaths:
        try:
            return self.games[game_id]
        except KeyError as error:
            raise LocalConfigError(
                f"Local game configuration does not define game: {game_id}"
            ) from error


def _load_game_paths(
    game_id: object, value: object, root: Path, config_path: Path
) -> LocalGamePaths:
    if not isinstance(game_id, str) or not game_id:
        raise LocalConfigError(f"Invalid game identifier in {config_path}: {game_id}")
    if not isinstance(value, dict):
        raise LocalConfigError(f"Invalid game entry in {config_path}: {game_id}")
    unknown = set(value) - {"patched_rom", "base_rom"}
    if unknown:
        fields = ", ".join(sorted(unknown))
        raise LocalConfigError(f"Unknown fields for {game_id} in {config_path}: {fields}")
    patched_rom = _resolve_path(value.get("patched_rom"), root, game_id, "patched_rom")
    base_rom = _resolve_path(
        value.get("base_rom"), root, game_id, "base_rom", optional=True
    )
    return LocalGamePaths(game_id, patched_rom, base_rom)


def _resolve_path(
    value: object,
    root: Path,
    game_id: str,
    field: str,
    *,
    optional: bool = False,
) -> Path | None:
    if value is None and optional:
        return None
    if not isinstance(value, str) or not value.strip():
        raise LocalConfigError(f"Game {game_id} must define a non-empty {field}")
    path = Path(value)
    return (path if path.is_absolute() else root / path).resolve()

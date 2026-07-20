from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any
import unicodedata

from romwiki.errors import DataSourceError


class PokeDBGeneration:
    def __init__(
        self,
        *,
        pokemon_by_id: dict[int, dict[str, Any]],
        pokemon_by_name: dict[str, dict[str, Any]],
        pokemon_by_species: dict[str, dict[str, Any]],
        abilities_by_id: dict[int, str],
        items_by_id: dict[int, str],
        items_by_lookup: dict[str, str] | None = None,
        moves_by_id: dict[int, str] | None = None,
    ) -> None:
        self.pokemon_by_id = pokemon_by_id
        self.pokemon_by_name = pokemon_by_name
        self.pokemon_by_species = pokemon_by_species
        self.abilities_by_id = abilities_by_id
        self.items_by_id = items_by_id
        self.items_by_lookup = items_by_lookup or {
            _lookup_key(name): name for name in items_by_id.values()
        }
        self.moves_by_id = moves_by_id or {}

    @classmethod
    def load(cls, root: Path) -> PokeDBGeneration:
        resolved = root.resolve()
        defaults = _load_objects(resolved / "pokemon" / "default")
        variants = _load_objects(resolved / "pokemon" / "variant")
        abilities = _load_objects(resolved / "ability")
        items = _load_objects(resolved / "item")
        moves = _load_objects(resolved / "move")
        pokemon_by_id = {item["id"]: item for item in defaults}
        pokemon_by_name = {item["name"]: item for item in (*defaults, *variants)}
        if len(pokemon_by_id) != len(defaults):
            raise DataSourceError("PokéDB default Pokémon IDs must be unique")
        return cls(
            pokemon_by_id=pokemon_by_id,
            pokemon_by_name=pokemon_by_name,
            pokemon_by_species={item["species"]: item for item in defaults},
            abilities_by_id=_id_name_map(abilities, "ability"),
            items_by_id=_id_name_map(items, "item"),
            items_by_lookup={_lookup_key(item["name"]): item["name"] for item in items},
            moves_by_id=_id_name_map(moves, "move"),
        )

    def pokemon_for_id(self, pokemon_id: int) -> dict[str, Any]:
        try:
            return self.pokemon_by_id[pokemon_id]
        except KeyError as error:
            raise DataSourceError(f"PokéDB Pokémon ID does not exist: {pokemon_id}") from error

    def pokemon_for_name(self, name: str) -> dict[str, Any]:
        try:
            return self.pokemon_by_name[name]
        except KeyError as error:
            raise DataSourceError(f"PokéDB Pokémon does not exist: {name}") from error

    def pokemon_for_species(self, species: str) -> dict[str, Any]:
        try:
            return self.pokemon_by_species[species]
        except KeyError as error:
            raise DataSourceError(f"PokéDB species does not exist: {species}") from error

    def ability_name(self, ability_id: int) -> str | None:
        if ability_id == 0:
            return None
        try:
            return self.abilities_by_id[ability_id]
        except KeyError as error:
            raise DataSourceError(f"PokéDB ability ID does not exist: {ability_id}") from error

    def item_name(self, item_id: int) -> str | None:
        if item_id == 0:
            return None
        try:
            return self.items_by_id[item_id]
        except KeyError as error:
            raise DataSourceError(f"PokéDB item ID does not exist: {item_id}") from error

    def item_slug(self, rom_name: str) -> str:
        key = _lookup_key(rom_name)
        return self.items_by_lookup.get(key, _name_slug(rom_name))

    def move_name(self, move_id: int) -> str | None:
        if move_id == 0:
            return None
        try:
            return self.moves_by_id[move_id]
        except KeyError as error:
            raise DataSourceError(f"PokéDB move ID does not exist: {move_id}") from error

    def pokemon_sprite(
        self, reference: dict[str, Any], version: str | None
    ) -> dict[str, str] | None:
        sprites = reference.get("sprites")
        if not isinstance(sprites, dict):
            return None
        url = None
        if version:
            versions = sprites.get("versions")
            if isinstance(versions, dict):
                version_sprites = versions.get(version)
                if isinstance(version_sprites, dict):
                    url = version_sprites.get("front_default")
        if not url:
            url = sprites.get("front_default")
        if not isinstance(url, str) or not url.startswith("https://"):
            return None
        return {
            "url": url,
            "source": "PokéAPI sprites",
            "source_url": "https://github.com/PokeAPI/sprites",
        }


def _load_objects(directory: Path) -> list[dict[str, Any]]:
    if not directory.is_dir():
        raise DataSourceError(f"PokéDB directory does not exist: {directory}")
    objects = []
    for path in sorted(directory.glob("*.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(value, dict) or not isinstance(value.get("id"), int):
                raise DataSourceError(f"Invalid PokéDB object: {path}")
            objects.append(value)
        except json.JSONDecodeError as error:
            raise DataSourceError(f"Invalid PokéDB JSON: {path}") from error
    if not objects:
        raise DataSourceError(f"PokéDB directory contains no JSON objects: {directory}")
    return objects


def _id_name_map(objects: list[dict[str, Any]], resource: str) -> dict[int, str]:
    result = {item["id"]: item["name"] for item in objects}
    if len(result) != len(objects):
        raise DataSourceError(f"PokéDB {resource} IDs must be unique")
    return result


def _lookup_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", normalized.casefold())


def _name_slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", normalized.casefold()).strip("-")

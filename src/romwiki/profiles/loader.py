from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any

from romwiki.platforms.registry import RomImage
from romwiki.profiles.models import (
    GameProfile,
    HashMatch,
    KnownHash,
    LocationSectionConfig,
    TableSymbol,
    TypeChartConfig,
)
from romwiki.util.errors import ProfileError

_SLUG_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_SYMBOLS_DIRECTORY = "symbols"
_SYMBOL_SUFFIX = "_symbol"
_SPECIAL_SUFFIX = "_special"


class ProfileRepository:
    def __init__(self, profiles: tuple[GameProfile, ...]) -> None:
        self.profiles = profiles

    @classmethod
    def load(cls, directory: Path) -> ProfileRepository:
        if not directory.is_dir():
            raise ProfileError(f"Profile directory does not exist: {directory}")
        # `symbols/` holds the generated pret symbol subsets profiles resolve
        # against, not profiles.
        paths = sorted(
            path
            for path in directory.rglob("*.toml")
            if _SYMBOLS_DIRECTORY not in path.relative_to(directory).parts[:-1]
        )
        if not paths:
            raise ProfileError(f"No TOML profiles found in: {directory}")

        raw_profiles = {path: _read_profile_data(path) for path in paths}
        profiles_by_id: dict[str, tuple[Path, dict[str, Any]]] = {}
        for path, data in raw_profiles.items():
            try:
                profile_id = data["profile"]["id"]
            except (KeyError, TypeError) as error:
                raise ProfileError(f"Invalid profile {path}: {error}") from error
            if not isinstance(profile_id, str) or not profile_id:
                raise ProfileError(f"Invalid profile identifier in {path}")
            if profile_id in profiles_by_id:
                raise ProfileError("Profile identifiers must be unique")
            profiles_by_id[profile_id] = path, data

        resolved: dict[str, dict[str, Any]] = {}

        def resolve(profile_id: str, ancestors: tuple[str, ...] = ()) -> dict[str, Any]:
            if profile_id in resolved:
                return resolved[profile_id]
            if profile_id in ancestors:
                chain = " -> ".join((*ancestors, profile_id))
                raise ProfileError(f"Profile inheritance cycle: {chain}")
            try:
                path, data = profiles_by_id[profile_id]
            except KeyError as error:
                raise ProfileError(
                    f"Profile extends unknown profile: {profile_id}"
                ) from error
            profile_data = data.get("profile")
            if not isinstance(profile_data, dict):
                raise ProfileError(f"Invalid profile metadata in {path}")
            parent_id = profile_data.get("extends")
            if parent_id is None:
                merged = _merge_tables({}, data)
            else:
                if not isinstance(parent_id, str) or not parent_id:
                    raise ProfileError(f"Invalid profile parent in {path}")
                if "hashes" not in data:
                    raise ProfileError(
                        f"Inherited profile {profile_id} must define its own hashes"
                    )
                if parent_id not in profiles_by_id:
                    raise ProfileError(
                        f"Profile {profile_id} extends unknown profile {parent_id}"
                    )
                parent = resolve(parent_id, (*ancestors, profile_id))
                if "type_chart" in parent and "type_chart" not in data:
                    raise ProfileError(
                        f"Inherited profile {profile_id} must explicitly declare "
                        "its type chart"
                    )
                merged = _merge_tables(
                    parent,
                    data,
                )
                # A variant contract records that this exact build's trainer
                # selectors were verified, which a parent's verification does
                # not show; without its own, a profile publishes no families.
                if "trainer_variant_contract" not in data.get("parameters", {}):
                    merged.get("parameters", {}).pop("trainer_variant_contract", None)
            merged["profile"].pop("extends", None)
            resolved[profile_id] = merged
            return merged

        symbol_tables: dict[str, dict[str, Any]] = {}
        profiles = tuple(
            _build_profile(
                path, _resolve_symbols(resolve(profile_id), directory, symbol_tables)
            )
            for profile_id, (path, _) in profiles_by_id.items()
        )
        return cls(profiles)

    def identify(
        self, image: RomImage, *, platform: str | None = None
    ) -> HashMatch | None:
        """Match `image` against profiles, optionally only those for `platform`."""
        matches = [
            match
            for profile in self.profiles
            if (platform is None or profile.platform == platform)
            and (match := profile.match(image)) is not None
        ]
        if len(matches) > 1:
            raise ProfileError("ROM image matches more than one profile")
        return matches[0] if matches else None


def _resolve_symbols(
    data: dict[str, Any],
    directory: Path,
    tables: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Turn `<name>_symbol` parameters into `<name>_offset` and `<name>_special`
    handler names into `gSpecials` indices, from the profile's symbol table.

    An explicit `<name>_offset` wins over an inherited symbol, which is how a
    hack overrides a table it moved.
    """
    parameters = dict(data.get("parameters", {}))
    symbol_keys = [key for key in parameters if key.endswith(_SYMBOL_SUFFIX)]
    special_keys = [
        key
        for key, value in parameters.items()
        if key.endswith(_SPECIAL_SUFFIX) and isinstance(value, str)
    ]
    if not symbol_keys and not special_keys:
        return data
    table_name = data["profile"].get("symbols")
    if not isinstance(table_name, str):
        raise ProfileError(
            f"Profile {data['profile'].get('id')} names symbols without a symbol table"
        )
    if table_name not in tables:
        tables[table_name] = _read_profile_data(
            directory / _SYMBOLS_DIRECTORY / f"{table_name}.toml"
        )
    table = tables[table_name]
    sources: dict[str, TableSymbol] = {}
    for key in symbol_keys:
        symbol = parameters.pop(key)
        offset_key = key.removesuffix(_SYMBOL_SUFFIX) + "_offset"
        if offset_key in parameters:
            continue
        try:
            entry = table["symbols"][symbol]
            parameters[offset_key] = entry["offset"]
        except KeyError as error:
            raise ProfileError(
                f"Symbol table {table_name} has no symbol {symbol!r}"
            ) from error
        sources[offset_key] = TableSymbol(
            name=symbol,
            address=entry.get("address"),
            pointers=tuple(entry.get("pointers", ())),
        )
    for key in special_keys:
        try:
            parameters[key] = table["specials"][parameters[key]]
        except KeyError as error:
            raise ProfileError(
                f"Symbol table {table_name} has no special {parameters[key]!r}"
            ) from error
    return {**data, "parameters": parameters, "symbol_sources": sources}


def _read_profile_data(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as stream:
            data = tomllib.load(stream)
    except tomllib.TOMLDecodeError as error:
        raise ProfileError(f"Invalid profile {path}: {error}") from error
    if not isinstance(data, dict):
        raise ProfileError(f"Invalid profile data in {path}")
    return data


def _merge_tables(parent: dict[str, Any], child: dict[str, Any]) -> dict[str, Any]:
    merged = dict(parent)
    for key, value in child.items():
        inherited = merged.get(key)
        if isinstance(inherited, dict) and isinstance(value, dict):
            merged[key] = _merge_tables(inherited, value)
        else:
            merged[key] = value
    return merged


def _build_profile(path: Path, data: dict[str, Any]) -> GameProfile:
    try:
        profile_data = data["profile"]
        header_data = data["header"]
        reference_data = data.get("reference", {})
        if not isinstance(reference_data, dict):
            raise ProfileError(f"Invalid reference metadata in {path}")
        sprite_version = reference_data.get("sprite_version")
        if sprite_version is not None and (
            not isinstance(sprite_version, str)
            or _SLUG_PATTERN.fullmatch(sprite_version) is None
        ):
            raise ProfileError(f"Invalid sprite version in {path}: {sprite_version}")
        semantics_data = data.get("semantics", {})
        if not isinstance(semantics_data, dict):
            raise ProfileError(f"Invalid semantic metadata in {path}")
        type_names = _load_semantic_names(
            semantics_data.get("types", {}), path, "type", 0xFF
        )
        move_names = _load_semantic_names(
            semantics_data.get("moves", {}), path, "move", 0xFFFF
        )
        type_chart = _load_type_chart(data.get("type_chart"), path)
        location_sections = _load_location_sections(data.get("location_sections"), path)
        hashes = tuple(
            KnownHash(
                algorithm=item["algorithm"].lower(),
                value=item["value"].lower(),
                variant=item["variant"],
            )
            for item in data.get("hashes", [])
        )
        if not hashes:
            raise ProfileError("Profile must contain at least one known hash")
        for known_hash in hashes:
            if known_hash.algorithm not in {"md5", "sha1", "sha256"}:
                raise ProfileError(
                    f"Unsupported hash algorithm: {known_hash.algorithm}"
                )
        return GameProfile(
            id=profile_data["id"],
            name=profile_data["name"],
            platform=profile_data["platform"],
            engine=profile_data["engine"],
            base_game=profile_data["base_game"],
            game_codes=tuple(header_data["game_codes"]),
            rom_versions=tuple(header_data["rom_versions"]),
            hashes=hashes,
            sprite_version=sprite_version,
            type_names=type_names,
            move_names=move_names,
            type_chart=type_chart,
            location_sections=location_sections,
            layout=dict(data.get("layout", {})),
            parameters=dict(data.get("parameters", {})),
            symbols=dict(data.get("symbol_sources", {})),
        )
    except (KeyError, TypeError) as error:
        raise ProfileError(f"Invalid profile {path}: {error}") from error


def _load_location_sections(value: object, path: Path) -> LocationSectionConfig:
    if value is None:
        return LocationSectionConfig()
    if not isinstance(value, dict) or set(value) - {
        "by_header",
        "by_internal_name",
    }:
        raise ProfileError(f"Invalid location section metadata in {path}")
    raw_by_header = value.get("by_header", {})
    raw_by_internal_name = value.get("by_internal_name", {})
    if not isinstance(raw_by_header, dict) or not isinstance(
        raw_by_internal_name, dict
    ):
        raise ProfileError(f"Invalid location section metadata in {path}")

    by_header: dict[int, str] = {}
    for raw_header_id, name in raw_by_header.items():
        try:
            header_id = int(raw_header_id)
        except (TypeError, ValueError) as error:
            raise ProfileError(
                f"Invalid location section header ID in {path}: {raw_header_id}"
            ) from error
        if header_id < 0 or not isinstance(name, str) or not name.strip():
            raise ProfileError(
                f"Invalid location section in {path}: {raw_header_id} = {name!r}"
            )
        by_header[header_id] = name.strip()

    by_internal_name: dict[str, str] = {}
    for internal_name, name in raw_by_internal_name.items():
        if (
            not isinstance(internal_name, str)
            or not internal_name.strip()
            or not isinstance(name, str)
            or not name.strip()
        ):
            raise ProfileError(
                f"Invalid location section in {path}: {internal_name!r} = {name!r}"
            )
        by_internal_name[internal_name] = name.strip()
    return LocationSectionConfig(by_header, by_internal_name)


def _load_semantic_names(
    value: object, path: Path, label: str, maximum_id: int
) -> dict[int, str]:
    if not isinstance(value, dict):
        raise ProfileError(f"Invalid {label} semantics in {path}")
    result = {}
    for raw_id, name in value.items():
        try:
            semantic_id = int(raw_id)
        except (TypeError, ValueError) as error:
            raise ProfileError(f"Invalid {label} ID in {path}: {raw_id}") from error
        if (
            not 0 <= semantic_id <= maximum_id
            or not isinstance(name, str)
            or _SLUG_PATTERN.fullmatch(name) is None
            or semantic_id in result
        ):
            raise ProfileError(f"Invalid {label} semantic in {path}: {raw_id} = {name}")
        result[semantic_id] = name
    return result


def _load_type_chart(value: object, path: Path) -> TypeChartConfig | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ProfileError(f"Invalid type chart metadata in {path}")
    chart = value.get("chart")
    additional_types = value.get("additional_types", ())
    overrides = value.get("overrides", {})
    if (
        not isinstance(chart, str)
        or _SLUG_PATTERN.fullmatch(chart) is None
        or not isinstance(additional_types, (list, tuple))
        or not all(
            isinstance(name, str) and _SLUG_PATTERN.fullmatch(name)
            for name in additional_types
        )
        or len(set(additional_types)) != len(additional_types)
        or not isinstance(overrides, dict)
        or not all(
            isinstance(key, str) and isinstance(item, str)
            for key, item in overrides.items()
        )
    ):
        raise ProfileError(f"Invalid type chart metadata in {path}")
    return TypeChartConfig(chart, tuple(additional_types), dict(overrides))

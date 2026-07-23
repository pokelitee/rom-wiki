from __future__ import annotations

from pathlib import Path
import re
import tomllib

from romwiki.util.errors import ProfileError
from romwiki.platforms.registry import RomImage
from romwiki.profiles.models import GameProfile, HashMatch, KnownHash


class ProfileRepository:
    def __init__(self, profiles: tuple[GameProfile, ...]) -> None:
        self.profiles = profiles

    @classmethod
    def load(cls, directory: Path) -> ProfileRepository:
        if not directory.is_dir():
            raise ProfileError(f"Profile directory does not exist: {directory}")
        profiles = tuple(
            _load_profile(path) for path in sorted(directory.rglob("*.toml"))
        )
        if not profiles:
            raise ProfileError(f"No TOML profiles found in: {directory}")
        identifiers = [profile.id for profile in profiles]
        if len(identifiers) != len(set(identifiers)):
            raise ProfileError("Profile identifiers must be unique")
        return cls(profiles)

    def identify(self, image: RomImage) -> HashMatch | None:
        matches = [
            match
            for profile in self.profiles
            if (match := profile.match(image)) is not None
        ]
        if len(matches) > 1:
            raise ProfileError("ROM image matches more than one profile")
        return matches[0] if matches else None


def _load_profile(path: Path) -> GameProfile:
    try:
        with path.open("rb") as stream:
            data = tomllib.load(stream)
        profile_data = data["profile"]
        header_data = data["header"]
        reference_data = data.get("reference", {})
        if not isinstance(reference_data, dict):
            raise ProfileError(f"Invalid reference metadata in {path}")
        sprite_version = reference_data.get("sprite_version")
        if sprite_version is not None and (
            not isinstance(sprite_version, str)
            or re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", sprite_version) is None
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
            layout=dict(data.get("layout", {})),
            parameters=dict(data.get("parameters", {})),
        )
    except (KeyError, TypeError, tomllib.TOMLDecodeError) as error:
        raise ProfileError(f"Invalid profile {path}: {error}") from error


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
            or re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) is None
            or semantic_id in result
        ):
            raise ProfileError(
                f"Invalid {label} semantic in {path}: {raw_id} = {name}"
            )
        result[semantic_id] = name
    return result

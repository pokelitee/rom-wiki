from __future__ import annotations

from pathlib import Path
import tomllib

from romwiki.errors import ProfileError
from romwiki.platforms.nds.reader import NintendoDSImage
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

    def identify(self, image: NintendoDSImage) -> HashMatch | None:
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
            engine=profile_data["engine"],
            base_game=profile_data["base_game"],
            game_codes=tuple(header_data["game_codes"]),
            rom_versions=tuple(header_data["rom_versions"]),
            hashes=hashes,
            layout=dict(data.get("layout", {})),
        )
    except (KeyError, TypeError, tomllib.TOMLDecodeError) as error:
        raise ProfileError(f"Invalid profile {path}: {error}") from error

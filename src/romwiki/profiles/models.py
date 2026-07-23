from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Mapping

from romwiki.platforms.registry import RomImage, get_platform


@dataclass(frozen=True, slots=True)
class KnownHash:
    algorithm: str
    value: str
    variant: str


@dataclass(frozen=True, slots=True)
class GameProfile:
    id: str
    name: str
    platform: str
    engine: str
    base_game: str
    game_codes: tuple[str, ...]
    rom_versions: tuple[int, ...]
    hashes: tuple[KnownHash, ...]
    sprite_version: str | None = None
    type_names: Mapping[int, str] = field(default_factory=dict)
    move_names: Mapping[int, str] = field(default_factory=dict)
    layout: Mapping[str, str] = field(default_factory=dict)
    parameters: Mapping[str, int] = field(default_factory=dict)

    def match(self, image: RomImage) -> HashMatch | None:
        platform = get_platform(self.platform)
        if not platform.matches_header(image, self.game_codes, self.rom_versions):
            return None
        image_hashes = image.hashes.to_dict()
        for known_hash in self.hashes:
            if image_hashes.get(known_hash.algorithm) == known_hash.value:
                return HashMatch(profile=self, known_hash=known_hash)
        return None


@dataclass(frozen=True, slots=True)
class HashMatch:
    profile: GameProfile
    known_hash: KnownHash

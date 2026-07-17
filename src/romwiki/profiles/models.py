from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Mapping

from romwiki.platforms.nds.reader import NintendoDSImage


@dataclass(frozen=True, slots=True)
class KnownHash:
    algorithm: str
    value: str
    variant: str


@dataclass(frozen=True, slots=True)
class GameProfile:
    id: str
    name: str
    engine: str
    base_game: str
    game_codes: tuple[str, ...]
    rom_versions: tuple[int, ...]
    hashes: tuple[KnownHash, ...]
    layout: Mapping[str, str] = field(default_factory=dict)
    parameters: Mapping[str, int] = field(default_factory=dict)

    def match(self, image: NintendoDSImage) -> HashMatch | None:
        if image.header.game_code not in self.game_codes:
            return None
        if image.header.rom_version not in self.rom_versions:
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

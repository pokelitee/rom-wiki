from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from romwiki.platforms.nds.reader import NintendoDSImage
from romwiki.profiles.loader import ProfileRepository
from romwiki.profiles.models import HashMatch


@dataclass(frozen=True, slots=True)
class InspectionResult:
    image: NintendoDSImage
    match: HashMatch | None

    def to_dict(self) -> dict[str, Any]:
        result = self.image.to_dict()
        result["profile"] = (
            {
                "id": self.match.profile.id,
                "name": self.match.profile.name,
                "engine": self.match.profile.engine,
                "base_game": self.match.profile.base_game,
                "variant": self.match.known_hash.variant,
                "matched_by": self.match.known_hash.algorithm,
            }
            if self.match
            else None
        )
        return result


def inspect_rom(rom_path: Path, profiles_dir: Path) -> InspectionResult:
    image = NintendoDSImage.inspect(rom_path)
    profiles = ProfileRepository.load(profiles_dir)
    return InspectionResult(image=image, match=profiles.identify(image))


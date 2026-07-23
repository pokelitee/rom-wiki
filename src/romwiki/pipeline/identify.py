from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from romwiki.platforms.registry import RomImage, get_platform
from romwiki.profiles.loader import ProfileRepository
from romwiki.profiles.models import HashMatch
from romwiki.util.errors import ProfileError


_DEFAULT_PLATFORM = "nintendo-ds"


@dataclass(frozen=True, slots=True)
class InspectionResult:
    image: RomImage
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
    image = get_platform(_DEFAULT_PLATFORM).inspect(rom_path)
    profiles = ProfileRepository.load(profiles_dir)
    match = profiles.identify(image)
    if match is not None and match.profile.platform != _DEFAULT_PLATFORM:
        raise ProfileError(
            f"Profile {match.profile.id} declares platform "
            f"{match.profile.platform!r}, but the image was opened as "
            f"{_DEFAULT_PLATFORM!r}"
        )
    return InspectionResult(image=image, match=match)


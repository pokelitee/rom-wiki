from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from romwiki.platforms.registry import RomImage, registered_platforms
from romwiki.profiles.loader import ProfileRepository
from romwiki.profiles.models import HashMatch
from romwiki.util.errors import InvalidRomError


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
    image, image_platform = _inspect_image(rom_path)
    profiles = ProfileRepository.load(profiles_dir)
    match = profiles.identify(image, platform=image_platform)
    return InspectionResult(image=image, match=match)


def _inspect_image(rom_path: Path) -> tuple[RomImage, str]:
    """Open `rom_path` with the first registered platform that accepts it."""
    failures = []
    for platform_id, adapter in registered_platforms().items():
        try:
            return adapter.inspect(rom_path), platform_id
        except InvalidRomError as error:
            failures.append(f"{platform_id}: {error}")
    detail = "; ".join(failures) or "no platforms are registered"
    raise InvalidRomError(f"No registered platform accepts {rom_path.name} ({detail})")

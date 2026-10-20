from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from romwiki.platforms.registry import RomImage, get_platform
from romwiki.util.errors import ProfileError


@dataclass(frozen=True, slots=True)
class KnownHash:
    algorithm: str
    value: str
    variant: str


@dataclass(frozen=True, slots=True)
class TypeChartConfig:
    chart: str
    additional_types: tuple[str, ...] = ()
    overrides: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TableSymbol:
    """The pret symbol a table offset was resolved from.

    `address` is the retail build's runtime address of the table and
    `pointers` the offsets in the retail ROM that hold it; both are empty
    where the symbol table records no pointer sites.
    """

    name: str
    address: int | None = None
    pointers: tuple[int, ...] = ()


class TableLocation(StrEnum):
    """How a symbol-named table was found in a specific ROM image."""

    # Every retail pointer site holds the symbol's own address.
    SYMBOL = "symbol"
    # Every site agrees on another address: the table was moved.
    POINTER = "pointer"
    # The sites disagree or hold no address in the image, so the retail
    # symbol offset is used unconfirmed.
    SYMBOL_UNCONFIRMED = "symbol-unconfirmed"


@dataclass(frozen=True, slots=True)
class LocationSectionConfig:
    """Profile-owned human labels for exact map-header sections."""

    by_header: Mapping[int, str] = field(default_factory=dict)
    by_internal_name: Mapping[str, str] = field(default_factory=dict)


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
    # The profile this one extends, or None for a retail game.
    parent: str | None = None
    sprite_version: str | None = None
    type_names: Mapping[int, str] = field(default_factory=dict)
    move_names: Mapping[int, str] = field(default_factory=dict)
    type_chart: TypeChartConfig | None = None
    location_sections: LocationSectionConfig = field(
        default_factory=LocationSectionConfig
    )
    layout: Mapping[str, str] = field(default_factory=dict)
    parameters: Mapping[str, Any] = field(default_factory=dict)
    # `<name>_offset` parameter -> the pret symbol it was resolved from.
    symbols: Mapping[str, TableSymbol] = field(default_factory=dict)
    # `<name>_offset` parameter -> how it was located in the matched image;
    # empty until `locate_tables` runs.
    table_locations: Mapping[str, TableLocation] = field(default_factory=dict)

    def int_parameter(self, name: str, default: int | None = None) -> int:
        """Return an integer parameter, or `default` when the profile omits it.

        Raises `ProfileError` when the value is missing without a default or
        is not an integer.
        """
        value = self.optional_int_parameter(name)
        if value is not None:
            return value
        if default is None:
            raise ProfileError(f"Profile {self.id!r} is missing parameter {name!r}")
        return default

    def optional_int_parameter(self, name: str) -> int | None:
        """Return an integer parameter, or None when the profile omits it."""
        value = self.parameters.get(name)
        if value is None:
            return None
        if not isinstance(value, int) or isinstance(value, bool):
            raise ProfileError(
                f"Profile {self.id!r} parameter {name!r} must be an integer, "
                f"not {type(value).__name__}"
            )
        return value

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
    # None when the image matched its profile by header only: an unknown
    # build whose data is read as the retail game's, unverified.
    known_hash: KnownHash | None

    @property
    def verified(self) -> bool:
        return self.known_hash is not None

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from romwiki.util.errors import SiteError

SiteKind = Literal["portal", "game"]
_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass(frozen=True, slots=True)
class GameMetadata:
    profiles: tuple[str, ...]
    generation: int
    base_game: str
    platform: str
    platform_name: str
    creator: str
    theme: str


@dataclass(frozen=True, slots=True)
class SiteDefinition:
    id: str
    name: str
    kind: SiteKind
    slug: str
    published: bool
    order: int
    config_path: Path
    description: str
    game: GameMetadata | None = None

    def output_path(self, output_root: Path) -> Path:
        return output_root / self.slug if self.slug else output_root


class SiteCatalog:
    def __init__(self, root: Path, sites: tuple[SiteDefinition, ...]) -> None:
        self.root = root
        self.sites = sites

    @classmethod
    def load(cls, root: Path) -> SiteCatalog:
        resolved_root = root.resolve()
        sites_root = resolved_root / "sites"
        descriptor_paths = [sites_root / "portal" / "site.toml"]
        games_root = sites_root / "games"
        if games_root.is_dir():
            descriptor_paths.extend(sorted(games_root.glob("*/game.toml")))

        sites = tuple(
            sorted(
                (_load_site(path, resolved_root) for path in descriptor_paths),
                key=lambda site: (site.order, site.id),
            )
        )
        _validate_catalog(sites)
        return cls(resolved_root, sites)

    def get(self, site_id: str) -> SiteDefinition:
        for site in self.sites:
            if site.id == site_id:
                return site
        raise SiteError(f"Unknown site: {site_id}")

    def published(self) -> tuple[SiteDefinition, ...]:
        return tuple(site for site in self.sites if site.published)


def _load_site(path: Path, root: Path) -> SiteDefinition:
    if not path.is_file():
        raise SiteError(f"Site descriptor does not exist: {path.relative_to(root)}")
    try:
        with path.open("rb") as stream:
            data = tomllib.load(stream)["site"]
        kind = data["kind"]
        if kind not in {"portal", "game"}:
            raise SiteError(f"Invalid site kind in {path}: {kind}")
        slug = data["slug"]
        if slug and not _SLUG_PATTERN.fullmatch(slug):
            raise SiteError(f"Invalid site slug in {path}: {slug}")
        config_path = (path.parent / data["mkdocs_config"]).resolve()
        if not config_path.is_relative_to(root) or not config_path.is_file():
            raise SiteError(f"Invalid MkDocs configuration for {path}")
        return SiteDefinition(
            id=data["id"],
            name=data["name"],
            kind=kind,
            slug=slug,
            published=data["published"],
            order=data["order"],
            config_path=config_path,
            description=data.get("description", ""),
            game=_load_game_metadata(path, root) if kind == "game" else None,
        )
    except (KeyError, TypeError, tomllib.TOMLDecodeError) as error:
        raise SiteError(f"Invalid site descriptor {path}: {error}") from error


def _load_game_metadata(path: Path, root: Path) -> GameMetadata:
    try:
        with path.open("rb") as stream:
            data = tomllib.load(stream)
        game = data["game"]
        appearance = data["appearance"]
        generation = game["generation"]
        if not isinstance(generation, int) or generation < 1:
            raise SiteError(f"Invalid game generation in {path.relative_to(root)}")
        raw_profiles = game["profile"] if "profile" in game else game["profiles"]
        profiles = (
            (raw_profiles,) if isinstance(raw_profiles, str) else tuple(raw_profiles)
        )
        if not profiles or not all(isinstance(value, str) for value in profiles):
            raise SiteError(f"Invalid profile(s) in {path.relative_to(root)}")
        slug_fields: dict[str, Any] = {
            "base_game": game["base_game"],
            "platform": game["platform"],
            "theme": appearance["theme"],
        }
        for profile in profiles:
            if not _SLUG_PATTERN.fullmatch(profile):
                raise SiteError(
                    f"Invalid profile in {path.relative_to(root)}: {profile}"
                )
        for field_name, value in slug_fields.items():
            if not isinstance(value, str) or not _SLUG_PATTERN.fullmatch(value):
                raise SiteError(
                    f"Invalid {field_name} in {path.relative_to(root)}: {value}"
                )
        creator = game["creator"]
        if not isinstance(creator, str) or not creator.strip():
            raise SiteError(f"Invalid creator in {path.relative_to(root)}")
        platform_name = game["platform_name"]
        if not isinstance(platform_name, str) or not platform_name.strip():
            raise SiteError(f"Invalid platform name in {path.relative_to(root)}")
        return GameMetadata(
            profiles=profiles,
            generation=generation,
            base_game=slug_fields["base_game"],
            platform=slug_fields["platform"],
            platform_name=platform_name.strip(),
            creator=creator.strip(),
            theme=slug_fields["theme"],
        )
    except (KeyError, TypeError, tomllib.TOMLDecodeError) as error:
        raise SiteError(f"Invalid game metadata {path}: {error}") from error


def _validate_catalog(sites: tuple[SiteDefinition, ...]) -> None:
    if sum(site.kind == "portal" for site in sites) != 1:
        raise SiteError("The site catalog must contain exactly one portal")
    if any(site.kind == "portal" and site.slug for site in sites):
        raise SiteError("The portal slug must be empty")
    identifiers = [site.id for site in sites]
    if len(identifiers) != len(set(identifiers)):
        raise SiteError("Site identifiers must be unique")
    slugs = [site.slug for site in sites]
    if len(slugs) != len(set(slugs)):
        raise SiteError("Site slugs must be unique")
    if any(site.kind == "game" and site.game is None for site in sites):
        raise SiteError("Every game site must include game metadata")

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import tomllib
from typing import Literal

from romwiki.errors import SiteError


SiteKind = Literal["portal", "game"]
_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass(frozen=True, slots=True)
class SiteDefinition:
    id: str
    name: str
    kind: SiteKind
    slug: str
    published: bool
    order: int
    config_path: Path

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
        )
    except (KeyError, TypeError, tomllib.TOMLDecodeError) as error:
        raise SiteError(f"Invalid site descriptor {path}: {error}") from error


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

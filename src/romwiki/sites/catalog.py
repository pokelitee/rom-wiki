from __future__ import annotations

import re
import tomllib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from romwiki.engines.registry import get_engine
from romwiki.pipeline.build.sections import DATASET_KINDS, enabled_dataset_kinds
from romwiki.profiles.loader import ProfileRepository
from romwiki.util.errors import SiteError

SiteKind = Literal["portal", "game"]
_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SUPPORTED_THEMES = frozenset(
    {
        "black-2-white-2",
        "black-white",
        "heart-gold-soul-silver",
        "platinum",
        "portal",
    }
)
DEFAULT_GENERATED_SECTIONS = (
    *DATASET_KINDS,
    "types",
    "data",
)
_GENERATED_SECTION_SET = frozenset(DEFAULT_GENERATED_SECTIONS)


@dataclass(frozen=True, slots=True)
class GameMetadata:
    profiles: tuple[str, ...]
    versions: tuple[str, ...]
    data_driven: bool
    generation: int
    base_game: str
    platform: str
    platform_name: str
    creator: str
    generated_sections: tuple[str, ...] = DEFAULT_GENERATED_SECTIONS


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
    theme: str
    game: GameMetadata | None = None

    def output_path(self, output_root: Path) -> Path:
        return output_root / self.slug if self.slug else output_root


def site_display_key(site: SiteDefinition) -> tuple[bool, int, int, str]:
    generation = site.game.generation if site.game is not None else 0
    return site.kind != "portal", generation, site.order, site.id


class SiteCatalog:
    def __init__(
        self,
        root: Path,
        sites: tuple[SiteDefinition, ...],
        profile_repository: ProfileRepository | None = None,
    ) -> None:
        self.root = root
        self.sites = sites
        self.profile_repository = profile_repository

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
                key=site_display_key,
            )
        )
        _validate_catalog(sites)
        profiles = _load_profile_repository(resolved_root)
        _validate_profile_references(sites, profiles)
        return cls(resolved_root, sites, profiles)

    def get(self, site_id: str) -> SiteDefinition:
        for site in self.sites:
            if site.id == site_id:
                return site
        raise SiteError(f"Unknown site: {site_id}")

    def published(self) -> tuple[SiteDefinition, ...]:
        return tuple(site for site in self.sites if site.published)

    def select(
        self,
        site_ids: Sequence[str] = (),
        *,
        all_published: bool = False,
    ) -> tuple[SiteDefinition, ...]:
        if all_published and site_ids:
            raise SiteError("Specify site identifiers or --all, not both")
        if not all_published and not site_ids:
            raise SiteError("Specify at least one site identifier or --all")
        selected = (
            self.published()
            if all_published
            else tuple(self.get(site_id) for site_id in site_ids)
        )
        if len({site.id for site in selected}) != len(selected):
            raise SiteError("A site may only be selected once")
        return selected


def _load_site(path: Path, root: Path) -> SiteDefinition:
    if not path.is_file():
        raise SiteError(f"Site descriptor does not exist: {path.relative_to(root)}")
    try:
        with path.open("rb") as stream:
            descriptor = tomllib.load(stream)
        site = descriptor["site"]
        kind = site["kind"]
        if kind not in {"portal", "game"}:
            raise SiteError(f"Invalid site kind in {path}: {kind}")
        slug = site["slug"]
        if slug and not _SLUG_PATTERN.fullmatch(slug):
            raise SiteError(f"Invalid site slug in {path}: {slug}")
        theme = descriptor["appearance"]["theme"]
        if not isinstance(theme, str) or not _SLUG_PATTERN.fullmatch(theme):
            raise SiteError(f"Invalid theme in {path.relative_to(root)}: {theme}")
        if theme not in SUPPORTED_THEMES:
            raise SiteError(f"Unsupported theme in {path.relative_to(root)}: {theme}")
        config_path = (path.parent / site["mkdocs_config"]).resolve()
        if not config_path.is_relative_to(root) or not config_path.is_file():
            raise SiteError(f"Invalid MkDocs configuration for {path}")
        return SiteDefinition(
            id=site["id"],
            name=site["name"],
            kind=kind,
            slug=slug,
            published=site["published"],
            order=site["order"],
            config_path=config_path,
            description=site.get("description", ""),
            theme=theme,
            game=(
                _load_game_metadata(path, root, descriptor["game"])
                if kind == "game"
                else None
            ),
        )
    except (KeyError, TypeError, tomllib.TOMLDecodeError) as error:
        raise SiteError(f"Invalid site descriptor {path}: {error}") from error


def _load_game_metadata(
    path: Path,
    root: Path,
    game: dict[str, Any],
) -> GameMetadata:
    try:
        generation = game["generation"]
        if not isinstance(generation, int) or generation < 1:
            raise SiteError(f"Invalid game generation in {path.relative_to(root)}")
        data_driven = game.get("data_driven", True)
        if not isinstance(data_driven, bool):
            raise SiteError(f"Invalid data_driven flag in {path.relative_to(root)}")
        raw_profiles = game.get("profile", game.get("profiles", ()))
        profiles = (
            (raw_profiles,) if isinstance(raw_profiles, str) else tuple(raw_profiles)
        )
        raw_versions = game.get("versions", ())
        versions = tuple(raw_versions) if isinstance(raw_versions, list) else ()
        if (data_driven and not profiles) or not all(
            isinstance(value, str) for value in profiles
        ):
            raise SiteError(f"Invalid profile(s) in {path.relative_to(root)}")
        if len(profiles) > 1 and (
            len(versions) != len(profiles)
            or not all(
                isinstance(value, str) and _SLUG_PATTERN.fullmatch(value)
                for value in versions
            )
        ):
            raise SiteError(
                f"Version-family site must define one valid version label per "
                f"profile in {path.relative_to(root)}"
            )
        if len(profiles) <= 1 and versions:
            raise SiteError(
                f"Single-profile site cannot define versions in "
                f"{path.relative_to(root)}"
            )
        slug_fields: dict[str, Any] = {
            "base_game": game["base_game"],
            "platform": game["platform"],
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
        raw_sections = game.get("generated_sections", DEFAULT_GENERATED_SECTIONS)
        generated_sections = (
            tuple(raw_sections) if isinstance(raw_sections, (list, tuple)) else ()
        )
        if (
            not generated_sections
            or len(generated_sections) != len(set(generated_sections))
            or not all(
                isinstance(section, str) and section in _GENERATED_SECTION_SET
                for section in generated_sections
            )
        ):
            raise SiteError(f"Invalid generated_sections in {path.relative_to(root)}")
        for required in ("pokemon", "types", "data"):
            if data_driven and required not in generated_sections:
                raise SiteError(
                    f"Data-driven game in {path.relative_to(root)} must require "
                    f"generated section {required!r}"
                )
        return GameMetadata(
            profiles=profiles,
            versions=versions,
            data_driven=data_driven,
            generation=generation,
            base_game=slug_fields["base_game"],
            platform=slug_fields["platform"],
            platform_name=platform_name.strip(),
            creator=creator.strip(),
            generated_sections=generated_sections,
        )
    except (KeyError, TypeError) as error:
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


def _load_profile_repository(root: Path) -> ProfileRepository | None:
    profiles_root = root / "profiles"
    if not profiles_root.is_dir():
        return None
    return ProfileRepository.load(profiles_root)


def _validate_profile_references(
    sites: tuple[SiteDefinition, ...],
    repository: ProfileRepository | None,
) -> None:
    if repository is None:
        return
    profiles = {profile.id: profile for profile in repository.profiles}
    for site in sites:
        if site.game is None or not site.game.data_driven:
            continue
        missing = [
            profile_id
            for profile_id in site.game.profiles
            if profile_id not in profiles
        ]
        if missing:
            raise SiteError(
                f"Game site {site.id} references unknown profile(s): "
                f"{', '.join(missing)}"
            )
        selected = [profiles[profile_id] for profile_id in site.game.profiles]
        if any(profile.platform != site.game.platform for profile in selected):
            raise SiteError(f"Game site {site.id} platform does not match its profiles")
        if len({profile.engine for profile in selected}) != 1:
            raise SiteError(f"Game site {site.id} profiles must use the same engine")
        engine = get_engine(selected[0].engine)
        if engine.generation is None:
            raise SiteError(
                f"Game site {site.id} uses an engine without generation metadata"
            )
        if engine.generation != site.game.generation:
            raise SiteError(
                f"Game site {site.id} generation does not match its profiles"
            )
        enabled_by_profile = {
            profile.id: enabled_dataset_kinds(profile) for profile in selected
        }
        enabled_sets = set(enabled_by_profile.values())
        if len(enabled_sets) != 1:
            raise SiteError(
                f"Game site {site.id} profiles enable different dataset sections"
            )
        declared = frozenset(
            section
            for section in site.game.generated_sections
            if section in DATASET_KINDS
        )
        expected = frozenset(next(iter(enabled_sets)))
        if declared != expected:
            raise SiteError(
                f"Game site {site.id} generated_sections do not match its "
                f"profile sections: expected {', '.join(sorted(expected))}"
            )

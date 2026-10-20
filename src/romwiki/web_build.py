"""Build one game's frontend bundle from a ROM, entirely in memory.

This is the entry point the browser generator runs: it reads nothing but the
ROMs, the repository's profiles and site descriptors, and PokéDB, and writes
nothing; the caller stores the returned files.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from romwiki import __version__
from romwiki.engines.registry import get_engine
from romwiki.pipeline.build.workflow import GameBuildWorkflow
from romwiki.pipeline.enrichment.type_charts import build_type_dataset
from romwiki.pipeline.extraction.identify import InspectionResult, inspect_rom
from romwiki.profiles.loader import ProfileRepository
from romwiki.profiles.models import GameProfile
from romwiki.sites.catalog import SiteCatalog, SiteDefinition
from romwiki.sites.data_exports import public_dataset_file
from romwiki.sites.frontend import (
    FRONTEND_SCHEMA_VERSION,
    FrontendGame,
    read_site_documents,
    render_game,
)
from romwiki.sources import PokeDBGeneration
from romwiki.util.errors import ProfileError

PokeDBLoader = Callable[[int], PokeDBGeneration]
_FALLBACK_THEME = "portal"


def build_wiki(
    rom: Path,
    *,
    root: Path,
    pokedb: PokeDBLoader,
    base_rom: Path | None = None,
) -> dict[str, bytes]:
    """Return a frontend bundle (`path -> bytes`) for the game in `rom`.

    `root` holds the repository's `profiles/` and site descriptors, and
    `pokedb(generation)` loads PokéDB for a generation. A ROM no profile
    knows is read as the retail game its header names and marked
    unverified. With `base_rom`, every section is compared with it.
    """
    profiles = ProfileRepository.load(root / "profiles")
    current = inspect_rom(
        rom, root / "profiles", profiles=profiles, allow_unverified=True
    )
    if current.match is None:
        raise ProfileError(f"{rom.name} is not a supported game")
    baseline = None
    if base_rom is not None:
        baseline = inspect_rom(base_rom, root / "profiles", profiles=profiles)
        if baseline.match is None:
            raise ProfileError(f"{base_rom.name} is not a known base game")
    profile = current.match.profile
    generation = get_engine(profile.engine).generation
    if generation is None:
        raise ProfileError(f"Engine {profile.engine!r} has no PokéDB generation")
    datasets, comparisons = _build(current, baseline, pokedb(generation))

    site = _published_site(root, profile)
    reuse_site = (
        site is not None
        and current.match.verified
        and site.game is not None
        and site.game.profiles == (profile.id,)
    )
    download_entries = []
    download_files = {}
    for kind, dataset in sorted(datasets.items()):
        path, payload, entry = public_dataset_file(kind, dataset)
        download_entries.append(entry)
        download_files[path] = payload
    if reuse_site:
        assert site is not None and site.game is not None
        game = FrontendGame(
            id=site.id,
            name=site.name,
            description=site.description,
            generation=site.game.generation,
            theme=site.theme,
            mascot=site.mascot,
            versions=tuple(site.game.versions),
            datasets=datasets,
            comparisons=comparisons,
            requires_comparisons=baseline is not None,
            download_entries=download_entries,
            download_files=download_files,
            documents=read_site_documents(root, site),
        )
    else:
        game = FrontendGame(
            id=profile.id,
            name=profile.name,
            description=f"Generated from your copy of {profile.name}.",
            generation=generation,
            theme=site.theme if site is not None else _FALLBACK_THEME,
            mascot=site.mascot if site is not None else None,
            versions=(profile.base_game,),
            datasets=datasets,
            comparisons=comparisons,
            requires_comparisons=baseline is not None,
            download_entries=download_entries,
            download_files=download_files,
            documents=(),
        )

    files: dict[str, bytes] = {}
    entry = render_game(game, files.__setitem__)
    manifest = {
        "schema_version": FRONTEND_SCHEMA_VERSION,
        "mascot": entry["mascot"],
        "games": [entry],
        "local": {
            "profile": profile.id,
            "verified": current.match.verified,
            "rom_sha256": current.image.hashes.to_dict().get("sha256"),
            "generator_version": __version__,
        },
    }
    files["manifest.json"] = (
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")
    return files


def _build(
    current: InspectionResult,
    baseline: InspectionResult | None,
    pokedb: PokeDBGeneration,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    assert current.match is not None
    workflow = GameBuildWorkflow(
        current, pokedb, baseline=baseline, baseline_cache_root=None
    )
    builds = workflow.build_all()
    datasets = {kind: build.current for kind, build in builds.items()}
    datasets["types"] = build_type_dataset(current.match.profile)
    comparisons = {
        kind: build.comparison
        for kind, build in builds.items()
        if build.comparison is not None
    }
    # Repository builds publish data as JSON and read it back; doing the same
    # here gives the renderer identical values (lists, not tuples).
    return _as_json(datasets), _as_json(comparisons)


def _as_json(value: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = json.loads(json.dumps(value))
    return result


def _published_site(root: Path, profile: GameProfile) -> SiteDefinition | None:
    """The published site whose game includes `profile`."""
    for site in SiteCatalog.load(root).published():
        if site.game is not None and profile.id in site.game.profiles:
            return site
    return None

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mkdocs.config.defaults import MkDocsConfig
from mkdocs.structure.files import Files
from mkdocs.structure.pages import Page

from romwiki.sites.catalog import SiteCatalog, SiteDefinition
from romwiki.sites.dev_pages import DevPages
from romwiki.util.errors import SiteError

_catalog: SiteCatalog | None = None
_current_site: SiteDefinition | None = None
_dev_pages: DevPages | None = None


def on_config(config: MkDocsConfig) -> MkDocsConfig:
    global _catalog, _current_site, _dev_pages
    config_path = Path(config.config_file_path).resolve()
    root = _find_repository_root(config_path.parent)
    catalog = SiteCatalog.load(root)
    configured_site_id = config.extra.get("romwiki_site_id")
    current = (
        catalog.get(configured_site_id)
        if isinstance(configured_site_id, str)
        else next(
            (site for site in catalog.sites if site.config_path == config_path),
            None,
        )
    )
    if current is None:
        raise SiteError(f"MkDocs configuration is not registered: {config_path}")
    _catalog = catalog
    _current_site = current
    dev_pages_path = config.extra.get("romwiki_dev_pages")
    _dev_pages = (
        DevPages.load(config_path.parent / dev_pages_path)
        if isinstance(dev_pages_path, str)
        else None
    )
    config.extra["romwiki_site"] = _site_context(current)
    config.extra["romwiki_games"] = [
        _site_context(site)
        for site in catalog.published()
        if site.kind == "game"
    ]
    deployment_url = os.environ.get("ROMWIKI_SITE_URL")
    if deployment_url:
        config.site_url = _deployment_site_url(deployment_url, current)
    return config


def on_files(files: Files, config: MkDocsConfig) -> Files:
    if _dev_pages is None:
        return files
    return Files(
        file for file in files if _dev_pages.includes_document(file.src_uri)
    )


def on_page_context(
    context: dict[str, Any],
    page: Page,
    config: MkDocsConfig,
    nav: Any,
) -> dict[str, Any]:
    if _catalog is None or _current_site is None:
        return context
    depth = len([part for part in page.url.split("/") if part])
    artifact_root = "../" * (depth + (1 if _current_site.kind == "game" else 0))
    context["romwiki"] = {
        "current": _site_context(_current_site),
        "portal_url": artifact_root or "./",
        "games": [
            {
                **_site_context(site),
                "url": f"{artifact_root}{site.slug}/",
            }
            for site in _catalog.published()
            if site.kind == "game"
        ],
    }
    return context


def _find_repository_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "sites" / "portal" / "site.toml").is_file():
            return candidate
    raise SiteError(f"Could not locate ROM Wiki repository from {start}")


def _site_context(site: SiteDefinition) -> dict[str, Any]:
    game = site.game
    return {
        "id": site.id,
        "name": site.name,
        "kind": site.kind,
        "slug": site.slug,
        "description": site.description,
        "generation": game.generation if game else None,
        "base_game": game.base_game if game else None,
        "platform": game.platform if game else None,
        "platform_name": game.platform_name if game else None,
        "creator": game.creator if game else None,
        "theme": game.theme if game else "portal",
    }


def _deployment_site_url(root_url: str, site: SiteDefinition) -> str:
    root = root_url.rstrip("/") + "/"
    return f"{root}{site.slug}/" if site.kind == "game" else root

from __future__ import annotations

from pathlib import Path
from typing import Any

from mkdocs.config.defaults import MkDocsConfig
from mkdocs.structure.pages import Page

from romwiki.errors import SiteError
from romwiki.sites.catalog import SiteCatalog, SiteDefinition


_catalog: SiteCatalog | None = None
_current_site: SiteDefinition | None = None


def on_config(config: MkDocsConfig) -> MkDocsConfig:
    global _catalog, _current_site
    config_path = Path(config.config_file_path).resolve()
    root = _find_repository_root(config_path.parent)
    catalog = SiteCatalog.load(root)
    current = next(
        (site for site in catalog.sites if site.config_path == config_path),
        None,
    )
    if current is None:
        raise SiteError(f"MkDocs configuration is not registered: {config_path}")
    _catalog = catalog
    _current_site = current
    config.extra["romwiki_site"] = _site_context(current)
    return config


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
        "creator": game.creator if game else None,
        "theme": game.theme if game else "portal",
    }

from __future__ import annotations

import os
import posixpath
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from mkdocs.config.defaults import MkDocsConfig
from mkdocs.structure.files import Files
from mkdocs.structure.pages import Page

from romwiki.sites.catalog import SiteCatalog, SiteDefinition
from romwiki.sites.dev_pages import DevPages
from romwiki.util.errors import SiteError

_catalog: SiteCatalog | None = None
_current_site: SiteDefinition | None = None
_current_sections: set[str] = set()
_dev_pages: DevPages | None = None
_HREF = re.compile(r"""(\bhref\s*=\s*)(["'])(.*?)\2""", re.IGNORECASE)


def on_config(config: MkDocsConfig) -> MkDocsConfig:
    global _catalog, _current_site, _current_sections, _dev_pages
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
    _current_sections = _nav_sections(config.nav)
    dev_pages_path = config.extra.get("romwiki_dev_pages")
    _dev_pages = (
        DevPages.load(config_path.parent / dev_pages_path)
        if isinstance(dev_pages_path, str)
        else None
    )
    config.extra["romwiki_site"] = {
        **_site_context(current),
        "sections": sorted(_current_sections),
    }
    config.extra["romwiki_games"] = [
        _site_context(site) for site in catalog.published() if site.kind == "game"
    ]
    deployment_url = os.environ.get("ROMWIKI_SITE_URL")
    if deployment_url:
        config.site_url = _deployment_site_url(deployment_url, current)
    # pymdownx.snippets resolves relative base_path entries against the
    # process's current working directory, not the config file -- set it to
    # an absolute path here so shared partials resolve the same way
    # regardless of where `mkdocs build` is invoked from.
    config.mdx_configs.setdefault("pymdownx.snippets", {})["base_path"] = [
        str(root / "sites" / "shared" / "partials")
    ]
    return config


def on_files(files: Files, config: MkDocsConfig) -> Files:
    if _dev_pages is None:
        return files
    return Files(file for file in files if _dev_pages.includes_document(file.src_uri))


def on_page_content(
    html: str,
    page: Page,
    config: MkDocsConfig,
    files: Files,
) -> str:
    del config, files
    return _rewrite_markdown_links(html, page.file.src_uri, page.url)


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
        "current": {
            **_site_context(_current_site),
            "sections": sorted(_current_sections),
        },
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


def _rewrite_markdown_links(
    html: str,
    source_file: str,
    source_url: str,
) -> str:
    """Normalize local Markdown targets to their published URLs."""

    def replace(match: re.Match[str]) -> str:
        href = match.group(3)
        url = urlsplit(href)
        if (
            url.scheme
            or url.netloc
            or url.path.startswith("/")
            or not url.path.lower().endswith(".md")
        ):
            return match.group(0)
        target_file = posixpath.normpath(
            posixpath.join(posixpath.dirname(source_file), url.path)
        )
        target_url = (
            posixpath.dirname(target_file)
            if posixpath.basename(target_file).lower() == "index.md"
            else target_file.removesuffix(".md")
        )
        target_url += "/"
        published = posixpath.relpath(target_url.rstrip("/"), source_url.rstrip("/"))
        published += "/"
        rewritten = urlunsplit(("", "", published, url.query, url.fragment))
        return f"{match.group(1)}{match.group(2)}{rewritten}{match.group(2)}"

    return _HREF.sub(replace, html)


def _nav_sections(nav_config: Any) -> set[str]:
    """Top-level URL segments (e.g. "pokemon", "items") present in this
    site's `mkdocs.yml` nav -- lets shared templates skip section cards/
    links for datasets a game hasn't built yet, instead of assuming every
    game has full section coverage.
    """
    sections: set[str] = set()
    stack = [nav_config]
    while stack:
        item = stack.pop()
        if isinstance(item, str):
            segment = item.strip("/").split("/", 1)[0]
            if segment and segment != "index.md" and not segment.endswith(".md"):
                sections.add(segment)
        elif isinstance(item, dict):
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    return sections


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
        "data_driven": game.data_driven if game else False,
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

from __future__ import annotations

import hashlib
import json
import logging
import os
import posixpath
import re
import sqlite3
from bisect import bisect_right
from collections.abc import Iterator, Sequence
from concurrent.futures import ProcessPoolExecutor
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit

from romwiki.util.errors import SiteError

_LOG = logging.getLogger("romwiki")
_PAGE_PROGRESS_INTERVAL = 1_000
# Below this page count, process startup costs more than the parse it saves.
_PARALLEL_PAGE_THRESHOLD = 500
_PARSE_CHUNK_SIZE = 64

# minify_html drops attribute-value quotes whenever a value has no
# whitespace/quote/`=`/angle-bracket characters (e.g. `href=../..` instead of
# `href="../.."`), so every attribute-value match below accepts a quoted or a
# bareword value rather than assuming quotes are always present.
_ATTR_VALUE = r'(?:"([^"]*)"|\'([^\']*)\'|([^\s"\'=<>`]+))'
_CUSTOM_CLASS = re.compile(r"\brw-[a-zA-Z0-9_-]+\b")
_CUSTOM_CSS_CLASS = re.compile(r"\.((?:rw-)[a-zA-Z0-9_-]+)")
_CONDITIONALLY_RENDERED_CLASSES = frozenset(
    {
        "rw-party-card__gender--unknown",
        "rw-party-card__moves-empty",
        "rw-record-tree__placeholder",
    }
)
_EXTERNAL_SCHEMES = {"data", "http", "https", "mailto", "tel"}
_ID = re.compile(rf"\bid={_ATTR_VALUE}", re.IGNORECASE | re.DOTALL)
_HREF = re.compile(rf"<a\b[^>]*\bhref={_ATTR_VALUE}", re.IGNORECASE | re.DOTALL)
_CLASS = re.compile(rf"\bclass={_ATTR_VALUE}", re.IGNORECASE | re.DOTALL)
_SRC = re.compile(rf"\bsrc={_ATTR_VALUE}", re.IGNORECASE | re.DOTALL)
_LOADING = re.compile(rf"\bloading={_ATTR_VALUE}", re.IGNORECASE | re.DOTALL)
_IMAGE = re.compile(r"<img\b[^>]*>", re.IGNORECASE | re.DOTALL)
_DETAIL_TAG = re.compile(r"</?details\b[^>]*>|<summary\b[^>]*>", re.IGNORECASE)
_TABLE_TAG = re.compile(r"</?table\b[^>]*>|<th\b[^>]*>", re.IGNORECASE)
_HEADING = re.compile(r"<h([1-6])\b", re.IGNORECASE)


def _attr_value(match: re.Match[str]) -> str:
    return next(group for group in match.groups() if group is not None)


@dataclass(frozen=True)
class SiteAuditIssue:
    code: str
    path: str
    message: str
    line: int | None = None

    def format(self) -> str:
        location = f"{self.path}:{self.line}" if self.line else self.path
        return f"{location}: [{self.code}] {self.message}"


@dataclass(frozen=True)
class SiteAuditReport:
    page_count: int
    link_count: int
    total_html_bytes: int
    largest_page: tuple[str, int] | None
    errors: tuple[SiteAuditIssue, ...]
    warnings: tuple[SiteAuditIssue, ...]

    @property
    def ok(self) -> bool:
        return not self.errors


@dataclass
class _ParsedPage:
    ids: set[str]
    links: list[tuple[str, int]]
    custom_classes: set[str]
    issues: list[SiteAuditIssue]
    image_count: int


def _parse_page(text: str, path: str) -> _ParsedPage:
    newlines = [match.start() for match in re.finditer("\n", text)]
    line_at = lambda position: bisect_right(newlines, position) + 1
    issues: list[SiteAuditIssue] = []
    ids: set[str] = set()
    for match in _ID.finditer(text):
        identifier = _attr_value(match)
        if identifier in ids:
            issues.append(
                SiteAuditIssue(
                    "duplicate-id",
                    path,
                    f"duplicate id {identifier!r}",
                    line_at(match.start()),
                )
            )
        ids.add(identifier)

    links = [
        (_attr_value(match), line_at(match.start())) for match in _HREF.finditer(text)
    ]
    custom_classes = {
        class_name
        for match in _CLASS.finditer(text)
        for class_name in _CUSTOM_CLASS.findall(_attr_value(match))
    }
    images = list(_IMAGE.finditer(text))
    for match in images:
        tag = match.group(0)
        line = line_at(match.start())
        if not re.search(r"\balt\b(\s*=|\s|/?>)", tag, re.IGNORECASE):
            issues.append(
                SiteAuditIssue(
                    "image-alt", path, "image is missing an alt attribute", line
                )
            )
        source = _SRC.search(tag)
        if source and _attr_value(source).startswith(("http://", "https://")):
            loading = _LOADING.search(tag)
            if not loading or _attr_value(loading).lower() != "lazy":
                issues.append(
                    SiteAuditIssue(
                        "image-loading", path, "external image is not lazy-loaded", line
                    )
                )

    _audit_container_tags(
        text, path, newlines, _DETAIL_TAG, "details", "summary", issues
    )
    _audit_container_tags(text, path, newlines, _TABLE_TAG, "table", "th", issues)

    headings = [
        (int(match.group(1)), match.start()) for match in _HEADING.finditer(text)
    ]
    for (previous, _), (level, position) in zip(headings, headings[1:], strict=False):
        if level > previous + 1:
            issues.append(
                SiteAuditIssue(
                    "heading-order",
                    path,
                    f"heading level jumps from h{previous} to h{level}",
                    line_at(position),
                )
            )
    html_tag = re.search(r"<html\b[^>]*>", text, re.IGNORECASE)
    if not html_tag or not re.search(r"\blang\s*=", html_tag.group(0), re.IGNORECASE):
        issues.append(
            SiteAuditIssue("document-lang", path, "html element has no language", 1)
        )
    title = re.search(r"<title\b[^>]*>(.*?)</title>", text, re.IGNORECASE | re.DOTALL)
    if not title or not re.sub(r"<[^>]+>", "", title.group(1)).strip():
        issues.append(
            SiteAuditIssue("document-title", path, "document has no title", 1)
        )
    main_count = len(re.findall(r"<main\b", text, re.IGNORECASE))
    if main_count != 1:
        issues.append(
            SiteAuditIssue(
                "main-count", path, f"expected one main element, found {main_count}", 1
            )
        )
    h1_count = sum(level == 1 for level, _ in headings)
    if h1_count != 1:
        issues.append(
            SiteAuditIssue("h1-count", path, f"expected one h1, found {h1_count}", 1)
        )
    return _ParsedPage(ids, links, custom_classes, issues, len(images))


def _audit_container_tags(
    text: str,
    path: str,
    newlines: list[int],
    pattern: re.Pattern[str],
    container: str,
    required_child: str,
    issues: list[SiteAuditIssue],
) -> None:
    stack: list[tuple[int, bool]] = []
    for match in pattern.finditer(text):
        tag = match.group(0).lower()
        if tag.startswith(f"<{container}"):
            stack.append((match.start(), False))
        elif tag.startswith(f"<{required_child}") and stack:
            position, _ = stack[-1]
            stack[-1] = (position, True)
        elif tag.startswith(f"</{container}") and stack:
            position, found = stack.pop()
            if not found:
                code = "details-summary" if container == "details" else "table-header"
                message = (
                    "details element has no summary"
                    if container == "details"
                    else "table has no header cells"
                )
                issues.append(
                    SiteAuditIssue(
                        code,
                        path,
                        message,
                        bisect_right(newlines, position) + 1,
                    )
                )


def _read_and_parse(task: tuple[str, str]) -> tuple[str, int, _ParsedPage]:
    """Read one artifact page and parse it. Runs in a worker process."""
    root, relative = task
    page = Path(root) / relative
    return (
        relative,
        page.stat().st_size,
        _parse_page(page.read_text(encoding="utf-8"), relative),
    )


def _parse_worker_count(jobs: int | None, page_count: int) -> int:
    if jobs is not None and jobs < 1:
        raise SiteError(f"Parallel job count must be at least 1: {jobs}")
    if page_count < _PARALLEL_PAGE_THRESHOLD:
        return 1
    if jobs is not None:
        return min(jobs, page_count)
    return min(page_count, os.cpu_count() or 1)


def _read_digest(task: tuple[str, str]) -> tuple[str, str]:
    root, relative = task
    return relative, hashlib.sha256((Path(root) / relative).read_bytes()).hexdigest()


def _read_digest_and_parse(
    task: tuple[str, str],
) -> tuple[str, int, str, _ParsedPage]:
    root, relative = task
    data = (Path(root) / relative).read_bytes()
    return (
        relative,
        len(data),
        hashlib.sha256(data).hexdigest(),
        _parse_page(data.decode("utf-8"), relative),
    )


def _read_and_parse_tasks(
    tasks: Sequence[tuple[str, str]], worker_count: int
) -> list[tuple[str, int, str, _ParsedPage]]:
    if not tasks:
        return []
    workers = min(worker_count, len(tasks))
    if workers <= 1:
        return list(map(_read_digest_and_parse, tasks))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return list(
            pool.map(
                _read_digest_and_parse,
                tasks,
                chunksize=_PARSE_CHUNK_SIZE,
            )
        )


def _parsed_pages(
    tasks: Sequence[tuple[str, str]],
    *,
    jobs: int | None,
    cache_path: Path | None = None,
    refresh_cache: bool = False,
) -> Iterator[tuple[str, int, _ParsedPage]]:
    """Yield (relative path, byte size, parse result) in `tasks` order."""
    if cache_path is not None:
        yield from _cached_parsed_pages(
            tasks, jobs=jobs, cache_path=cache_path, refresh=refresh_cache
        )
        return
    worker_count = _parse_worker_count(jobs, len(tasks))
    if worker_count <= 1:
        yield from map(_read_and_parse, tasks)
        return
    _LOG.info("Parsing pages with %s parallel workers", worker_count)
    # Page parsing is pure regex over independent files, so it scales across
    # processes; the GIL keeps threads from helping here.
    with ProcessPoolExecutor(max_workers=worker_count) as pool:
        yield from pool.map(_read_and_parse, tasks, chunksize=_PARSE_CHUNK_SIZE)


def _cached_parsed_pages(
    tasks: Sequence[tuple[str, str]],
    *,
    jobs: int | None,
    cache_path: Path,
    refresh: bool,
) -> Iterator[tuple[str, int, _ParsedPage]]:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    parser_fingerprint = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    try:
        with closing(sqlite3.connect(cache_path)) as database:
            database.execute(
                "CREATE TABLE IF NOT EXISTS pages (path TEXT PRIMARY KEY, digest TEXT NOT NULL, parser TEXT NOT NULL, payload TEXT NOT NULL)"
            )
            cached = {} if refresh else {
                path: (digest, parser, payload)
                for path, digest, parser, payload in database.execute(
                    "SELECT path, digest, parser, payload FROM pages"
                )
            }
            worker_count = _parse_worker_count(jobs, len(tasks))
            if len(cached) < len(tasks) // 2:
                fresh = _read_and_parse_tasks(tasks, worker_count)
                fingerprints = {relative: digest for relative, _, digest, _ in fresh}
                parsed_misses = {
                    relative: (size, parsed)
                    for relative, size, _, parsed in fresh
                }
            else:
                if worker_count <= 1:
                    fingerprints = dict(map(_read_digest, tasks))
                else:
                    with ProcessPoolExecutor(max_workers=worker_count) as pool:
                        fingerprints = dict(
                            pool.map(
                                _read_digest,
                                tasks,
                                chunksize=_PARSE_CHUNK_SIZE,
                            )
                        )
                misses = [
                    task for task in tasks
                    if task[1] not in cached
                    or cached[task[1]][0] != fingerprints[task[1]]
                    or cached[task[1]][1] != parser_fingerprint
                ]
                fresh = _read_and_parse_tasks(misses, worker_count)
                parsed_misses = {
                    relative: (size, parsed)
                    for relative, size, _, parsed in fresh
                }
            for relative, (size, parsed) in parsed_misses.items():
                payload = json.dumps(
                    _parsed_page_to_dict(size, parsed), separators=(",", ":")
                )
                database.execute(
                    "INSERT OR REPLACE INTO pages VALUES (?, ?, ?, ?)",
                    (relative, fingerprints[relative], parser_fingerprint, payload),
                )
            current_paths = {relative for _, relative in tasks}
            database.executemany(
                "DELETE FROM pages WHERE path = ?",
                ((path,) for path in cached if path not in current_paths),
            )
            database.commit()
            for _, relative in tasks:
                if relative in parsed_misses:
                    size, parsed = parsed_misses[relative]
                else:
                    size, parsed = _parsed_page_from_dict(json.loads(cached[relative][2]))
                yield relative, size, parsed
    except (sqlite3.DatabaseError, json.JSONDecodeError, OSError, KeyError, TypeError):
        _LOG.warning("Audit cache is invalid; parsing all pages without reuse")
        yield from _parsed_pages(tasks, jobs=jobs)


def _parsed_page_to_dict(size: int, page: _ParsedPage) -> dict[str, object]:
    return {
        "size": size,
        "ids": sorted(page.ids),
        "links": page.links,
        "classes": sorted(page.custom_classes),
        "images": page.image_count,
        "issues": [issue.__dict__ for issue in page.issues],
    }


def _parsed_page_from_dict(value: dict[str, object]) -> tuple[int, _ParsedPage]:
    return int(value["size"]), _ParsedPage(
        set(value["ids"]),
        [tuple(link) for link in value["links"]],
        set(value["classes"]),
        [SiteAuditIssue(**issue) for issue in value["issues"]],
        int(value["images"]),
    )


def audit_site(
    root: Path,
    *,
    max_html_bytes: int = 512 * 1024,
    max_images_per_page: int = 150,
    base_url: str | None = None,
    jobs: int | None = None,
    cache_path: Path | None = None,
    refresh_cache: bool = False,
    expected_files: set[str] | None = None,
) -> SiteAuditReport:
    resolved_root = root.resolve()
    if not resolved_root.is_dir():
        raise SiteError(f"Site artifact does not exist: {resolved_root}")
    _LOG.info("Discovering site artifact files")
    artifact_files = [
        Path(directory) / name
        for directory, _, names in os.walk(resolved_root)
        for name in names
    ]
    _LOG.info("Discovered %s artifact files", f"{len(artifact_files):,}")
    html_files = sorted(
        path for path in artifact_files if path.suffix.lower() == ".html"
    )
    if not html_files:
        raise SiteError(f"Site artifact contains no HTML pages: {resolved_root}")

    existing_files = {
        path.relative_to(resolved_root).as_posix() for path in artifact_files
    }
    parsed: dict[str, _ParsedPage] = {}
    errors: list[SiteAuditIssue] = []
    warnings: list[SiteAuditIssue] = []
    total_bytes = 0
    largest_page: tuple[str, int] | None = None
    if expected_files is not None:
        for code, paths in (
            ("artifact-missing", expected_files - existing_files),
            ("artifact-unexpected", existing_files - expected_files),
        ):
            if paths:
                sample = ", ".join(sorted(paths)[:5])
                errors.append(
                    SiteAuditIssue(
                        code,
                        "artifact",
                        f"{len(paths):,} file(s); first: {sample}",
                    )
                )
    tasks = [
        (str(resolved_root), page.relative_to(resolved_root).as_posix())
        for page in html_files
    ]
    for page_number, (relative, size, result) in enumerate(
        _parsed_pages(
            tasks, jobs=jobs, cache_path=cache_path, refresh_cache=refresh_cache
        ), start=1
    ):
        total_bytes += size
        if largest_page is None or size > largest_page[1]:
            largest_page = (relative, size)
        if size > max_html_bytes:
            errors.append(
                SiteAuditIssue(
                    "page-size",
                    relative,
                    f"HTML is {size:,} bytes; limit is {max_html_bytes:,}",
                )
            )
        parsed[relative] = result
        errors.extend(result.issues)
        if result.image_count > max_images_per_page:
            warnings.append(
                SiteAuditIssue(
                    "image-count",
                    relative,
                    f"page has {result.image_count} images; limit is {max_images_per_page}",
                )
            )
        if page_number % _PAGE_PROGRESS_INTERVAL == 0:
            _LOG.info(
                "Audit parsed %s/%s pages",
                f"{page_number:,}",
                f"{len(html_files):,}",
            )

    link_count = 0
    total_links = sum(len(result.links) for result in parsed.values())
    _LOG.info("Validating %s links", f"{total_links:,}")
    base_path = unquote(urlsplit(base_url).path).rstrip("/") if base_url else ""
    for page, result in parsed.items():
        for href, line in result.links:
            link_count += 1
            issue = _validate_link(
                page, href, line, parsed, existing_files, base_path=base_path
            )
            if issue is not None:
                errors.append(issue)

    used_classes = set().union(*(page.custom_classes for page in parsed.values()))
    for asset in (path for path in artifact_files if path.suffix.lower() == ".js"):
        used_classes.update(_CUSTOM_CLASS.findall(asset.read_text(encoding="utf-8")))
    defined_classes: set[str] = set()
    for stylesheet in (
        path for path in artifact_files if path.suffix.lower() == ".css"
    ):
        defined_classes.update(
            _CUSTOM_CSS_CLASS.findall(stylesheet.read_text(encoding="utf-8"))
        )
    unused_classes = (
        defined_classes - used_classes - _CONDITIONALLY_RENDERED_CLASSES
    )
    for class_name in sorted(unused_classes):
        warnings.append(
            SiteAuditIssue(
                "css-unused",
                "assets",
                f"custom selector {class_name!r} is unused in the artifact",
            )
        )

    catalog_path = resolved_root / "games.json"
    if catalog_path.is_file():
        try:
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            games = catalog["games"]
            if catalog.get("schema_version") != 1 or not isinstance(games, list):
                raise ValueError
            slugs = [game["slug"] for game in games]
            if len(slugs) != len(set(slugs)) or not all(
                isinstance(slug, str) and f"{slug}/index.html" in existing_files
                for slug in slugs
            ):
                raise ValueError
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            errors.append(
                SiteAuditIssue(
                    "game-catalog", "games.json", "game catalog is invalid", 1
                )
            )

    return SiteAuditReport(
        page_count=len(html_files),
        link_count=link_count,
        total_html_bytes=total_bytes,
        largest_page=largest_page,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def _validate_link(
    source: str,
    href: str,
    line: int,
    parsed: dict[str, _ParsedPage],
    existing_files: set[str],
    *,
    base_path: str = "",
) -> SiteAuditIssue | None:
    url = urlsplit(href)
    if url.scheme.lower() in _EXTERNAL_SCHEMES or url.netloc:
        return None
    if url.scheme or href.startswith("javascript:"):
        return SiteAuditIssue(
            "link-scheme",
            source,
            f"unsupported link scheme in {href!r}",
            line,
        )
    if unquote(url.path).lower().endswith(".md"):
        return SiteAuditIssue(
            "published-markdown-link",
            source,
            f"published HTML links to a Markdown source: {href!r}",
            line,
        )
    target = (
        source
        if not url.path
        else _resolve_target(
            source, unquote(url.path), existing_files, base_path=base_path
        )
    )
    if target is None or target not in existing_files:
        return SiteAuditIssue(
            "link-target",
            source,
            f"local link target does not exist: {href!r}",
            line,
        )
    if url.fragment and target.lower().endswith(".html"):
        target_page = parsed.get(target)
        fragment = unquote(url.fragment)
        if target_page is None or fragment not in target_page.ids:
            return SiteAuditIssue(
                "link-fragment",
                source,
                f"fragment {fragment!r} does not exist in {href!r}",
                line,
            )
    return None


def _resolve_target(
    source: str,
    url_path: str,
    existing_files: set[str],
    *,
    base_path: str = "",
) -> str | None:
    if (
        url_path.startswith("/")
        and base_path
        and (url_path == base_path or url_path.startswith(f"{base_path}/"))
    ):
        url_path = url_path.removeprefix(base_path) or "/"
    if url_path.startswith("/"):
        target = url_path.lstrip("/")
    else:
        target = posixpath.join(posixpath.dirname(source), url_path)
    target = _finalize_target(target, url_path.endswith("/"), existing_files)
    if target == ".." or target.startswith("../"):
        return None
    if url_path.startswith("/") and target not in existing_files:
        source_site = source.partition("/")[0]
        site_target = _finalize_target(
            posixpath.join(source_site, url_path.lstrip("/")),
            url_path.endswith("/"),
            existing_files,
        )
        if site_target in existing_files:
            return site_target
        parts = url_path.strip("/").split("/")
        for index in range(len(parts)):
            suffix = _finalize_target(
                "/".join(parts[index:]), url_path.endswith("/"), existing_files
            )
            if suffix in existing_files:
                return suffix
    return target


def _finalize_target(
    target: str, directory_hint: bool, existing_files: set[str]
) -> str:
    target = posixpath.normpath(target)
    index_target = posixpath.normpath(posixpath.join(target, "index.html"))
    if directory_hint or (
        target not in existing_files and index_target in existing_files
    ):
        target = index_target
    return target

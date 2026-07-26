from __future__ import annotations

import posixpath
import re
from bisect import bisect_right
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit

from romwiki.util.errors import SiteError

# minify_html drops attribute-value quotes whenever a value has no
# whitespace/quote/`=`/angle-bracket characters (e.g. `href=../..` instead of
# `href="../.."`), so every attribute-value match below accepts a quoted or a
# bareword value rather than assuming quotes are always present.
_ATTR_VALUE = r'(?:"([^"]*)"|\'([^\']*)\'|([^\s"\'=<>`]+))'
_CUSTOM_CLASS = re.compile(r"\brw-[a-zA-Z0-9_-]+\b")
_CUSTOM_CSS_CLASS = re.compile(r"\.((?:rw-)[a-zA-Z0-9_-]+)")
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


def audit_site(
    root: Path,
    *,
    max_html_bytes: int = 512 * 1024,
    max_images_per_page: int = 150,
    base_url: str | None = None,
) -> SiteAuditReport:
    resolved_root = root.resolve()
    if not resolved_root.is_dir():
        raise SiteError(f"Site artifact does not exist: {resolved_root}")
    artifact_files = [path for path in resolved_root.rglob("*") if path.is_file()]
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
    for page in html_files:
        relative = page.relative_to(resolved_root).as_posix()
        size = page.stat().st_size
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
        result = _parse_page(page.read_text(encoding="utf-8"), relative)
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

    link_count = 0
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
    for asset in resolved_root.rglob("*.js"):
        used_classes.update(_CUSTOM_CLASS.findall(asset.read_text(encoding="utf-8")))
    defined_classes: set[str] = set()
    for stylesheet in resolved_root.rglob("*.css"):
        defined_classes.update(
            _CUSTOM_CSS_CLASS.findall(stylesheet.read_text(encoding="utf-8"))
        )
    for class_name in sorted(defined_classes - used_classes):
        warnings.append(
            SiteAuditIssue(
                "css-unused",
                "assets",
                f"custom selector {class_name!r} is unused in the artifact",
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

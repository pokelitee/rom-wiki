from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import PurePosixPath
import posixpath
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class EntityReference:
    kind: str
    id: int | str
    label: str
    route_key: int | str | None


@dataclass(frozen=True, slots=True)
class RouteDefinition:
    markdown: Callable[[int | str], str]
    published: Callable[[int | str], str]


class RouteResolver:
    def __init__(self, routes: dict[str, RouteDefinition]) -> None:
        self._routes = dict(routes)

    def markdown_href(self, reference: EntityReference, source_file: str) -> str | None:
        target = self._target(reference, published=False)
        if target is None:
            return None
        source_parent = str(PurePosixPath(source_file).parent)
        return posixpath.relpath(target, source_parent)

    def published_href(self, reference: EntityReference, source_url: str) -> str | None:
        target = self._target(reference, published=True)
        if target is None:
            return None
        return posixpath.relpath(target, source_url.rstrip("/")) + "/"

    def catalog_reference(
        self, reference: EntityReference, source_url: str
    ) -> dict[str, Any]:
        value: dict[str, Any] = {
            "kind": reference.kind,
            "id": reference.id,
            "label": reference.label,
        }
        url = self.published_href(reference, source_url)
        if url is not None:
            value["url"] = url
        return value

    def markdown_link(self, reference: EntityReference, source_file: str) -> str:
        label = _escape_markdown(reference.label)
        href = self.markdown_href(reference, source_file)
        return f"[{label}]({href})" if href is not None else label

    def html_link(self, reference: EntityReference, source_url: str) -> str:
        label = escape(reference.label)
        href = self.published_href(reference, source_url)
        if href is None:
            return label
        return f'<a href="{escape(href, quote=True)}">{label}</a>'

    def _target(self, reference: EntityReference, *, published: bool) -> str | None:
        if reference.route_key is None:
            return None
        definition = self._routes.get(reference.kind)
        if definition is None:
            return None
        factory = definition.published if published else definition.markdown
        return factory(reference.route_key).rstrip("/")


def entity_reference(
    kind: str,
    identifier: int | str,
    label: str,
    route_key: int | str | None,
) -> EntityReference:
    return EntityReference(kind, identifier, label, route_key)


def unique_references(
    references: list[EntityReference],
) -> list[EntityReference]:
    result = []
    seen = set()
    for reference in references:
        identity = (reference.kind, reference.id)
        if identity in seen:
            continue
        seen.add(identity)
        result.append(reference)
    return result


def _slug_route(section: str) -> RouteDefinition:
    return RouteDefinition(
        markdown=lambda key: f"{section}/{key}.md",
        published=lambda key: f"{section}/{key}/",
    )


ROUTES = RouteResolver(
    {
        "pokemon": _slug_route("pokemon"),
        "ability": _slug_route("abilities"),
        "item": _slug_route("items"),
        "move": _slug_route("moves"),
        "location": RouteDefinition(
            markdown=lambda key: f"locations/header-{int(key):03}.md",
            published=lambda key: f"locations/header-{int(key):03}/",
        ),
        "trainer": RouteDefinition(
            markdown=lambda key: f"trainers/trainer-{int(key):04}.md",
            published=lambda key: f"trainers/trainer-{int(key):04}/",
        ),
        "encounter": RouteDefinition(
            markdown=lambda key: f"encounters/area-{int(key):03}.md",
            published=lambda key: f"encounters/area-{int(key):03}/",
        ),
    }
)


def _escape_markdown(value: str) -> str:
    return value.replace("[", "\\[").replace("]", "\\]")

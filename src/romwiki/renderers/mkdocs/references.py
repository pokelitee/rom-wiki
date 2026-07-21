from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import PurePosixPath
import posixpath
from typing import Any, Callable, Iterable, Mapping


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
        label = escape_markdown(reference.label)
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


class ReferenceIndex:
    """Resolve normalized entity IDs to generated wiki routes."""

    def __init__(self, references: Iterable[EntityReference] = ()) -> None:
        self._references: dict[tuple[str, int | str], EntityReference] = {}
        for reference in references:
            self.add(reference)

    @classmethod
    def from_datasets(
        cls, datasets: Mapping[str, dict[str, Any]]
    ) -> ReferenceIndex:
        index = cls()
        for kind, dataset in datasets.items():
            route_kind = _DATASET_ROUTE_KINDS.get(kind)
            if route_kind is None:
                continue
            for record in dataset.get("records", []):
                reference = _record_reference(route_kind, record)
                if reference is None:
                    continue
                index.add(reference)
                if route_kind == "pokemon":
                    dex = record.get("national_dex_id")
                    if dex is not None:
                        index.add(
                            EntityReference(
                                route_kind,
                                dex,
                                reference.label,
                                reference.route_key,
                            )
                        )
        return index

    def add(self, reference: EntityReference) -> None:
        if reference.route_key is not None:
            self._references.setdefault((reference.kind, reference.id), reference)

    def resolve(
        self,
        kind: str,
        identifier: int | str,
        label: str,
        route_key: int | str | None = None,
    ) -> EntityReference:
        indexed = self._references.get((kind, identifier))
        return EntityReference(
            kind,
            identifier,
            label,
            indexed.route_key if indexed is not None else route_key,
        )


def entity_reference(
    kind: str,
    identifier: int | str,
    label: str,
    route_key: int | str | None,
) -> EntityReference:
    return EntityReference(kind, identifier, label, route_key)


def pokemon_markdown_link(
    identifier: int | str,
    label: str,
    route_key: int | str | None,
    source_file: str,
) -> str:
    return ROUTES.markdown_link(
        entity_reference("pokemon", identifier, label, route_key), source_file
    )


def resolved_reference(
    kind: str,
    identifier: int | str,
    label: str,
    route_key: int | str | None = None,
    *,
    index: ReferenceIndex | None = None,
) -> EntityReference:
    if index is None:
        return entity_reference(kind, identifier, label, route_key)
    return index.resolve(kind, identifier, label, route_key)


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


_DATASET_ROUTE_KINDS = {
    "pokemon": "pokemon",
    "abilities": "ability",
    "moves": "move",
    "items": "item",
    "encounters": "encounter",
    "trainers": "trainer",
    "locations": "location",
}


def _record_reference(
    kind: str, record: Mapping[str, Any]
) -> EntityReference | None:
    if kind in {"pokemon", "move"} and not record.get("public", True):
        return None
    identity_fields = {
        "pokemon": "member",
        "ability": "ability_id",
        "move": "move_id",
        "item": "item_id",
        "encounter": "area_id",
        "trainer": "trainer_id",
        "location": "header_id",
    }
    route_fields = {
        "pokemon": "slug",
        "ability": "slug",
        "move": "slug",
        "item": "slug",
        "encounter": "area_id",
        "trainer": "trainer_id",
        "location": "header_id",
    }
    identity = record.get(identity_fields[kind])
    if identity is None and kind == "pokemon":
        identity = record.get("national_dex_id")
    route_key = record.get(route_fields[kind])
    label = record.get("name") or record.get("label")
    if identity is None or route_key is None or not isinstance(label, str):
        return None
    return EntityReference(kind, identity, label, route_key)


def escape_markdown(value: str) -> str:
    return value.replace("[", "\\[").replace("]", "\\]")

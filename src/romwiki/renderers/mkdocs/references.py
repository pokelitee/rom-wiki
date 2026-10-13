from __future__ import annotations

import posixpath
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from html import escape
from pathlib import PurePosixPath
from typing import Any


@dataclass(frozen=True, slots=True)
class EntityReference:
    kind: str
    id: int | str
    label: str
    route_key: int | str | None
    sprite_url: str | None = None
    types: tuple[dict[str, Any], ...] | None = None


@dataclass(frozen=True, slots=True)
class RouteDefinition:
    markdown: Callable[[int | str], str]
    published: Callable[[int | str], str]


class RouteResolver:
    def __init__(self, routes: dict[str, RouteDefinition]) -> None:
        self._routes = dict(routes)

    def markdown_href(self, reference: EntityReference, source_file: str) -> str | None:
        """Resolve a link embedded in Markdown relative to its `.md` source."""
        if not source_file.endswith(".md"):
            raise ValueError(
                f"Markdown link source must be a .md file, got {source_file!r}"
            )
        target = self._target(reference, published=False)
        if target is None:
            return None
        source_parent = str(PurePosixPath(source_file).parent)
        return _relative_href(target, source_parent, trailing_slash=False)

    def published_href(self, reference: EntityReference, source_url: str) -> str | None:
        """Resolve raw HTML/catalog links relative to a published page URL."""
        if source_url and not source_url.endswith("/"):
            raise ValueError(
                f"Published link source must end in '/', got {source_url!r}"
            )
        target = self._target(reference, published=True)
        if target is None:
            return None
        return _relative_href(target, source_url.rstrip("/"), trailing_slash=True)

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
        return factory(reference.route_key)


class ReferenceIndex:
    """Resolve normalized entity IDs to generated wiki routes."""

    def __init__(self, references: Iterable[EntityReference] = ()) -> None:
        self._references: dict[tuple[str, int | str], EntityReference] = {}
        for reference in references:
            self.add(reference)

    @classmethod
    def from_datasets(cls, datasets: Mapping[str, dict[str, Any]]) -> ReferenceIndex:
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
                                reference.sprite_url,
                                reference.types,
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
            indexed.sprite_url if indexed is not None else None,
            indexed.types if indexed is not None else None,
        )

    def resolve_matching(
        self, kind: str, identifier: int | str, label: str
    ) -> EntityReference:
        indexed = self._references.get((kind, identifier))
        if indexed is None or indexed.label != label:
            return EntityReference(kind, identifier, label, None)
        return EntityReference(
            kind,
            identifier,
            label,
            indexed.route_key,
            indexed.sprite_url,
            indexed.types,
        )

    def sprite_url(self, kind: str, identifier: int | str) -> str | None:
        reference = self._references.get((kind, identifier))
        return reference.sprite_url if reference is not None else None

    def types(
        self, kind: str, identifier: int | str
    ) -> tuple[dict[str, Any], ...] | None:
        reference = self._references.get((kind, identifier))
        return reference.types if reference is not None else None


def entity_reference(
    kind: str,
    identifier: int | str,
    label: str,
    route_key: int | str | None,
) -> EntityReference:
    return EntityReference(kind, identifier, label, route_key)


def encounter_route_kind(route_key: int | str) -> str:
    """Select the route family for a normalized encounter page identity."""
    if isinstance(route_key, str) and route_key.startswith("header-"):
        return "encounter_location"
    return "encounter_variant" if isinstance(route_key, str) else "encounter"


def pokemon_markdown_link(
    identifier: int | str,
    label: str,
    route_key: int | str | None,
    source_file: str,
) -> str:
    return ROUTES.markdown_link(
        entity_reference("pokemon", identifier, label, route_key), source_file
    )


def pokemon_record_link(
    value: Mapping[str, Any],
    source_file: str,
    references: ReferenceIndex | None = None,
) -> str:
    """Link a Pokémon reference dict keyed by `id`/`slug`/`name` (fallback order).

    When `references` is given, resolves through it (`resolve_matching`)
    instead of trusting `slug` unconditionally -- a species beyond what the
    `pokemon` domain currently exposes as a public record (e.g. Generation
    III species past `PERSONAL_RECORD_COUNT`) has no real page, so this
    renders plain text rather than a dead link.
    """
    name = value["name"]
    if references is not None:
        # Different callers key their Pokémon dicts by "member" (the raw
        # engine-native species identifier, e.g. `personal_member_reference`'s
        # output) or by "id" (e.g. National Dex ID) -- `ReferenceIndex`
        # indexes "pokemon" records under both (see `from_datasets`), so try
        # "member" first, then "id".
        lookup_identifier = value.get("member", value.get("id", value.get("slug")))
        reference = references.resolve_matching("pokemon", lookup_identifier, name)
        return ROUTES.markdown_link(reference, source_file)
    identifier = value.get("id", value.get("slug", value["name"]))
    return pokemon_markdown_link(identifier, name, value.get("slug"), source_file)


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


def entity_markdown_link(
    kind: str,
    identifier: int | str,
    label: str,
    source_file: str,
    *,
    route_key: int | str | None = None,
    index: ReferenceIndex | None = None,
) -> str:
    """Render one Markdown link to an entity's generated page."""
    return ROUTES.markdown_link(
        resolved_reference(kind, identifier, label, route_key, index=index),
        source_file,
    )


def unique_references(
    references: Iterable[EntityReference],
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


def _anchored_slug_route(section: str) -> RouteDefinition:
    def target(key: int | str, suffix: str) -> str:
        path, separator, fragment = str(key).partition("#")
        return f"{section}/{path}{suffix}" + (f"#{fragment}" if separator else "")

    return RouteDefinition(
        markdown=lambda key: target(key, ".md"),
        published=lambda key: target(key, "/"),
    )


def _relative_href(target: str, source: str, *, trailing_slash: bool) -> str:
    path, separator, fragment = target.partition("#")
    href = posixpath.relpath(path.rstrip("/"), source)
    if trailing_slash:
        href += "/"
    if separator:
        href += f"#{fragment}"
    return href


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
        "encounter_variant": _anchored_slug_route("encounters"),
        "encounter_location": _anchored_slug_route("locations"),
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


def _record_reference(kind: str, record: Mapping[str, Any]) -> EntityReference | None:
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
    return EntityReference(
        kind,
        identity,
        label,
        route_key,
        _record_sprite_url(kind, record),
        _record_types(kind, record),
    )


def _record_sprite_url(kind: str, record: Mapping[str, Any]) -> str | None:
    if kind == "pokemon":
        sprite = record.get("sprite") or record.get("portrait")
        return sprite.get("url") if isinstance(sprite, Mapping) else None
    if kind == "item":
        reference = record.get("reference")
        if isinstance(reference, Mapping):
            sprite_url = reference.get("sprite_url")
            return sprite_url if isinstance(sprite_url, str) else None
    return None


def _record_types(
    kind: str, record: Mapping[str, Any]
) -> tuple[dict[str, Any], ...] | None:
    if kind != "pokemon":
        return None
    types = record.get("types")
    return tuple(types) if isinstance(types, list) else None


def escape_markdown(value: str) -> str:
    # `|` also needs neutralizing (not just `[`/`]`) since this value commonly
    # ends up inside a raw Markdown table cell via `markdown_link()`, where an
    # unescaped `|` would split the row — same rationale as
    # `components.escape_table_cell`.
    return value.replace("[", "\\[").replace("]", "\\]").replace("|", "&#124;")

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from romwiki.schema.enriched import EntityLink, MoveLink
from romwiki.sources import PokeDBGeneration
from romwiki.util.errors import DataSourceError
from romwiki.util.text import title_case_slug


def with_rom_description(
    reference: dict[str, Any] | None,
    description: str | None,
    *,
    label: str = "ROM description",
) -> dict[str, Any] | None:
    """Prefer the exact in-ROM prose while retaining structured reference data."""
    if not description or not description.strip():
        return reference
    enriched = dict(reference or {})
    enriched["flavor_text"] = description
    enriched["flavor_text_label"] = label
    enriched["flavor_text_source"] = "rom"
    return enriched


def item_reference(
    item_id: int,
    pokedb: PokeDBGeneration,
    item_names: list[str] | None,
    *,
    page_slugs: Mapping[int, str | None] | None = None,
) -> EntityLink:
    if item_id == 0:
        return {"id": 0, "slug": None, "name": None}
    if item_names is None:
        reference_slug = pokedb.item_name(item_id)
        if reference_slug is None:
            raise DataSourceError(f"Unknown item ID: {item_id}")
        page_slug = (
            page_slugs.get(item_id) if page_slugs is not None else reference_slug
        )
        return {
            "id": item_id,
            "slug": page_slug,
            "name": title_case_slug(reference_slug),
        }
    if item_id >= len(item_names):
        raise DataSourceError(f"Unknown item ID: {item_id}")
    name = item_names[item_id]
    slug: str | None = pokedb.item_slug(name)
    if page_slugs is not None:
        slug = page_slugs.get(item_id)
    return {"id": item_id, "slug": slug, "name": name}


def move_name(
    move_id: int,
    pokedb: PokeDBGeneration,
    move_names: Mapping[int, str] | None,
) -> str | None:
    if move_names is not None and move_id in move_names:
        return move_names[move_id]
    return pokedb.move_name(move_id)


def move_reference(
    move_id: int,
    pokedb: PokeDBGeneration,
    move_names: Mapping[int, str] | None,
    *,
    page_slugs: Mapping[int, str] | None = None,
) -> MoveLink | None:
    """Build a `{id, slug, name}` cross-reference to a move page.

    `slug` drives the display name (`title_case_slug`, preferring PokeDB's
    readable canonical name, e.g. "Solar Beam") -- but the actual `moves`
    page for a move whose ROM-decoded name diverges from PokeDB's ("SOLARBEAM"
    vs "Solar Beam") is generated under the ROM-derived slug (`moves.py`'s
    own `enrich_move_dataset` computes the identical value this function
    would get if `page_slugs` weren't overriding it). `page_slugs` (built
    from the real moves dataset the same way `item_reference`'s own
    `page_slugs` is) corrects the *link target* to the page that actually
    exists, without changing the nicer display text.
    """
    slug = move_name(move_id, pokedb, move_names)
    if slug is None:
        return None
    route_slug = page_slugs.get(move_id, slug) if page_slugs is not None else slug
    return {"id": move_id, "slug": route_slug, "name": title_case_slug(slug)}

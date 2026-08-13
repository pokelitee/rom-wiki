from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from romwiki.sources import PokeDBGeneration
from romwiki.util.errors import DataSourceError
from romwiki.util.text import title_case_slug


def item_reference(
    item_id: int,
    pokedb: PokeDBGeneration,
    item_names: list[str] | None,
    *,
    page_slugs: Mapping[int, str | None] | None = None,
) -> dict[str, Any]:
    if item_id == 0:
        return {"id": 0, "slug": None, "name": None}
    if item_names is None:
        reference_slug = pokedb.item_name(item_id)
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
    slug = pokedb.item_slug(name)
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

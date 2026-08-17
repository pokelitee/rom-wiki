from __future__ import annotations

import json
from typing import Any

from romwiki.renderers.mkdocs.components import display_name
from romwiki.renderers.mkdocs.references import (
    ROUTES,
    ReferenceIndex,
    resolved_reference,
)

PAGINATED_TABLE_THRESHOLD = 50
_SCHEMA_VERSION = 1
_PAGE_SIZE = 50


def paginated_table(
    *,
    columns: list[str],
    rows: list[list[dict[str, Any]]],
    fallback: list[str],
    table_key: str,
    label: str,
) -> list[str]:
    payload = json.dumps(
        {
            "schema_version": _SCHEMA_VERSION,
            "label": label,
            "page_param": f"{table_key}_page",
            "page_size": _PAGE_SIZE,
            "columns": columns,
            "rows": rows,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    payload = (
        payload.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    )
    return [
        '<div class="rw-learner-table" data-rw-learner-table markdown="1">',
        '<div class="rw-learner-table__interactive" '
        "data-rw-learner-interactive hidden></div>",
        '<script type="application/json" data-rw-learner-data>',
        payload,
        "</script>",
        '<div class="rw-learner-table__fallback" '
        'data-rw-learner-fallback markdown="1">',
        "",
        *fallback,
        "</div>",
        "</div>",
        "",
    ]


def pokemon_cell(
    value: dict[str, Any],
    source_file: str,
    references: ReferenceIndex | None,
) -> dict[str, Any]:
    identifier = value.get("member", value.get("id", value.get("slug", value["name"])))
    reference = resolved_reference(
        "pokemon",
        identifier,
        value["name"],
        value.get("slug"),
        index=references,
    )
    return {
        "kind": "pokemon",
        "label": value["name"],
        "url": ROUTES.published_href(reference, source_file.removesuffix(".md") + "/"),
        "sprite_url": reference.sprite_url,
    }


def pokemon_type_cell(
    value: dict[str, Any], references: ReferenceIndex | None
) -> dict[str, Any]:
    identifier = value.get("member", value.get("id"))
    types = (
        references.types("pokemon", identifier)
        if references is not None and identifier is not None
        else None
    )
    return {
        "kind": "types",
        "values": [
            {"name": str(type_["name"]), "label": display_name(str(type_["name"]))}
            for type_ in types or ()
        ],
    }


def text_cell(value: str) -> dict[str, str]:
    return {"kind": "text", "value": value}

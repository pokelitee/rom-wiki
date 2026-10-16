"""Publish the ROM-free, versioned data contract consumed by the React app."""

from __future__ import annotations

import gzip
import hashlib
import json
import re
import shutil
from collections.abc import Mapping
from dataclasses import asdict
from pathlib import Path
from typing import Any

from romwiki.pipeline.semantics.encounter_identity import (
    encounter_route_key,
    is_unlinked_encounter_area,
)
from romwiki.pipeline.transforms.comparisons import record_identity
from romwiki.pipeline.transforms.relationships import build_relationship_index
from romwiki.sites.catalog import SiteCatalog, SiteDefinition
from romwiki.sites.data_exports import validate_public_data
from romwiki.util.errors import SiteError
from romwiki.util.json_io import write_json_atomic

FRONTEND_SCHEMA_VERSION = 1
DETAIL_CHUNK_SIZE = 50
_SNIPPET = re.compile(r'^--8<--\s+"([^"]+)"\s*$', re.MULTILINE)
_FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)
_FRONTMATTER_TITLE = re.compile(r"^title:\s*(.+?)\s*$", re.MULTILINE)
_IDENTITY_FIELDS = {
    "pokemon": "member",
    "abilities": "ability_id",
    "moves": "move_id",
    "items": "item_id",
    "trainers": "trainer_id",
    "types": "id",
}


def record_route(kind: str, record: Mapping[str, Any]) -> str:
    if kind == "trainers":
        return f"trainer-{record['trainer_id']:04}"
    if kind == "locations":
        if "header_id" in record:
            return f"header-{record['header_id']:03}"
        return f"map-{record['map_index']:03}"
    if kind == "encounters":
        key = encounter_route_key(record)
        return f"area-{key:03}" if isinstance(key, int) else key
    if kind == "types":
        return str(record["name"])
    return str(record["slug"])


def _names(value: Any) -> list[str]:
    if isinstance(value, list):
        return list(dict.fromkeys(name for item in value for name in _names(item)))
    if isinstance(value, dict):
        return [str(value["name"])] if value.get("name") else []
    return [str(value)] if value is not None else []


def _search_text(value: str) -> str:
    """Lowercase published search text exactly as the frontend lowercases queries.

    `str.lower()` and JavaScript's `toLowerCase()` both apply Unicode default
    lowercasing. `casefold()` also expands characters such as "ß" to "ss",
    which a lowercased query can never match.
    """
    return value.lower()


def _search(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(
            _search(item)
            for key, item in value.items()
            if key not in {"provenance", "source", "reference", "sprite", "sprites"}
        )
    if isinstance(value, list):
        return " ".join(_search(item) for item in value)
    return str(value) if value is not None else ""


def _encounter_facets(record: dict[str, Any]) -> dict[str, Any]:
    methods: dict[str, list[str]] = {}
    levels: list[int] = []

    def collect(value: Any, method: str) -> None:
        if isinstance(value, list):
            for entry in value:
                collect(entry, method)
        elif isinstance(value, dict):
            pokemon = value.get("pokemon")
            if isinstance(pokemon, dict) and pokemon.get("name"):
                methods.setdefault(method, []).append(pokemon["name"])
            for key, entry in value.items():
                if key in {"minimum_level", "maximum_level", "level"} and isinstance(
                    entry, int
                ):
                    levels.append(entry)
                elif isinstance(entry, (dict, list)) and key not in {
                    "pokemon",
                    "provenance",
                    "location",
                    "locations",
                }:
                    collect(entry, method)

    variants = list(record.get("season_variants", {}).values()) or [record]
    for variant in variants:
        for method, value in variant.items():
            if isinstance(value, (dict, list)) and method not in {
                "provenance",
                "location",
                "locations",
                "version_variants",
            }:
                collect(value, method)
    fields: dict[str, Any] = {
        "methods": sorted(methods),
        "pokemon": sorted({name for names in methods.values() for name in names}),
    }
    if levels:
        fields.update(min_level=min(levels), max_level=max(levels))
    return fields


def _index_record(kind: str, record: dict[str, Any], route: str) -> dict[str, Any]:
    label = str(record.get("name") or route)
    if kind == "trainers":
        label = " ".join(
            str(record.get(key) or "") for key in ("class_name", "name")
        ).strip()
    fields: dict[str, Any] = {"name": label, "id": route}
    for key in (
        "types",
        "abilities",
        "egg_groups",
        "type",
        "damage_class",
        "pocket",
        "class_name",
        "season",
        "source_type",
    ):
        if key in record:
            fields[key] = _names(record[key])
    for key in ("power", "accuracy", "pp", "priority", "price", "national_dex_id"):
        if isinstance(record.get(key), (int, float)):
            fields[key] = record[key]
    stats = record.get("base_stats")
    if isinstance(stats, dict):
        fields["bst"] = sum(stats.values())
    if kind == "trainers":
        fields["battle_format"] = [
            {0: "single", 1: "double", 2: "triple", 3: "rotation"}.get(
                record.get("battle_mode", -1),
                "double" if record.get("double_battle") else "single",
            )
        ]
        fields["locations"] = _names(record.get("locations", []))
        party = record.get("party", [])
        fields["pokemon"] = _names([entry.get("pokemon", {}) for entry in party])
        levels = [
            entry["level"] for entry in party if isinstance(entry.get("level"), int)
        ]
        fields["party_size"] = len(party)
        if levels:
            fields.update(min_level=min(levels), max_level=max(levels))
    if kind == "locations":
        fields["section_name"] = record.get(
            "section_name", record.get("internal_name", "")
        )
        fields["features"] = [
            key
            for key in (
                "items",
                "shops",
                "trainers",
                "pokemon_gifts",
                "npc_trades",
                "static_encounters",
                "warps",
            )
            if record.get(key)
        ]
    if kind == "encounters":
        fields.update(_encounter_facets(record))
    return {
        "id": route,
        "label": label,
        "search": _search_text(
            " ".join([label, route, *(_search(value) for value in fields.values())])
        ),
        "fields": fields,
    }


def _write_resource(output: Path, prefix: str, value: Any) -> str:
    payload = (
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        + b"\n"
    )
    digest = hashlib.sha256(payload).hexdigest()[:16]
    relative = f"{prefix}-{digest}.json"
    path = output / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return relative


def _read_datasets(site: SiteDefinition) -> dict[str, dict[str, Any]]:
    data = site.config_path.parent / "wiki" / "data"
    validate_public_data(data.parent)
    manifest = json.loads((data / "manifest.json").read_text(encoding="utf-8"))
    return {
        (
            "encounters" if entry["kind"] == "wild_encounters" else entry["kind"]
        ): json.loads(gzip.decompress((data / entry["path"]).read_bytes()))
        for entry in manifest["files"]
    }


def _documentation(
    root: Path, site: SiteDefinition, output: Path
) -> list[dict[str, str]]:
    wiki = site.config_path.parent / "wiki"
    partials = (root / "sites/shared/partials").resolve()

    def expand(text: str, seen: frozenset[Path] = frozenset()) -> str:
        def snippet(match: re.Match[str]) -> str:
            path = (partials / match[1]).resolve()
            if not path.is_relative_to(partials) or path in seen or not path.is_file():
                raise SiteError(
                    f"Invalid or recursive documentation snippet: {match[1]}"
                )
            return expand(path.read_text(encoding="utf-8"), seen | {path})

        return _SNIPPET.sub(snippet, text)

    documents = []
    # A folder's index page introduces it, so it leads that folder's guides.
    paths = sorted(wiki.glob("*.md")) + sorted(
        (wiki / "docs").rglob("*.md"), key=lambda path: (path.stem != "index", path)
    )
    for path in paths:
        relative = path.relative_to(wiki).as_posix()
        slug = relative.removesuffix(".md")
        text = expand(path.read_text(encoding="utf-8"))
        frontmatter = _FRONTMATTER.match(text)
        if frontmatter:
            text = text[frontmatter.end() :]
        label = _document_label(path, frontmatter[1] if frontmatter else "", text)
        resource = _write_resource(output, f"{site.id}/docs/{slug}", {"markdown": text})
        documents.append(
            {"id": slug, "label": label, "path": resource, "search": _search_text(text)}
        )
    return documents


def _document_label(path: Path, frontmatter: str, text: str) -> str:
    """Title a guide by its frontmatter title, its first heading, or its file name."""
    title = _FRONTMATTER_TITLE.search(frontmatter)
    if title:
        return title[1].strip("\"'")
    heading = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    if heading:
        return heading[1]
    return path.stem.replace("-", " ").replace("_", " ").capitalize()


def _relationships(datasets: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index = build_relationship_index(datasets)
    result: dict[str, dict[str, Any]] = {}
    domains = {
        "pokemon": (
            "pokemon_wild_encounters",
            "pokemon_trainers",
            "pokemon_acquisition",
        ),
        "moves": ("move_level_up_learners", "move_machine_learners"),
        "locations": ("location_encounters",),
        "encounters": ("encounter_locations",),
    }
    for kind, names in domains.items():
        rows: dict[str, Any] = {}
        for name in names:
            for key, values in getattr(index, name).items():
                rows.setdefault(str(key), {})[
                    name.removeprefix(kind.removesuffix("s") + "_")
                ] = [asdict(value) for value in values]
        result[kind] = rows
    return result


def export_frontend(root: Path, output: Path, *, data_root: Path | None = None) -> int:
    """Write a content-addressed frontend bundle, rejecting incomplete comparisons.

    Existing normalized downloads remain independently versioned. Comparison
    inputs are supplied by local builds or restored data snapshots, never HTML.
    """
    root, output = root.resolve(), output.resolve()
    if output == root or root.is_relative_to(output):
        raise SiteError("Frontend output must not contain the repository")
    catalog = SiteCatalog.load(root)
    games = []
    for site in catalog.published():
        if site.game is None:
            continue
        datasets = _read_datasets(site)
        relationships = _relationships(datasets)
        sections: dict[str, Any] = {}
        comparisons: dict[str, str] = {}
        profile_id = site.game.profiles[0] if len(site.game.profiles) == 1 else site.id
        comparison_dir = site.config_path.parent / "wiki/data/comparisons"
        if data_root is not None:
            comparison_dir = data_root / profile_id / "comparisons"
        needs_comparison = site.id != site.game.base_game
        for kind, dataset in sorted(datasets.items()):
            comparison = None
            comparison_path = comparison_dir / f"{kind}.json"
            if comparison_path.is_file():
                comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
                if comparison.get("game") != dataset.get("game"):
                    raise SiteError(
                        f"Comparison belongs to a different game: {comparison_path}"
                    )
                routes = {
                    str(record_identity(str(dataset["dataset"]), record)): record_route(
                        kind, record
                    )
                    for record in dataset["records"]
                    if record.get("public", True)
                }
                comparison = {
                    **comparison,
                    "records": [
                        {**row, "route": routes.get(str(row["key"]))}
                        for row in comparison["records"]
                    ],
                }
                comparisons[kind] = _write_resource(
                    output, f"{site.id}/changes/{kind}", comparison
                )
            elif needs_comparison and kind != "types":
                raise SiteError(
                    f"Missing {site.id} {kind} comparison: {comparison_path}; regenerate or restore a complete data snapshot"
                )
            statuses = {
                str(row["key"]): row["status"]
                for row in (comparison or {}).get("records", [])
            }
            records = [
                record
                for record in dataset["records"]
                if record.get("public", True)
                and not (
                    kind == "encounters"
                    and is_unlinked_encounter_area(
                        record, dataset.get("encounter_format")
                    )
                )
            ]
            if kind == "encounters" and dataset.get("encounter_format") == "seasonal":
                seasonal: dict[str, dict[str, Any]] = {}
                for record in records:
                    key = record_route(kind, record)
                    if record.get("season"):
                        group = seasonal.setdefault(
                            key,
                            {
                                "name": record["name"],
                                "area_id": record["area_id"],
                                "map_index": record["map_index"],
                                "season_variants": {},
                            },
                        )
                        group["season_variants"][record["season"]] = record
                    else:
                        seasonal[key] = record
                records = list(seasonal.values())
            indexed: list[dict[str, Any]] = []
            seen = set()
            for start in range(0, len(records), DETAIL_CHUNK_SIZE):
                chunk = {}
                entries = []
                for record in records[start : start + DETAIL_CHUNK_SIZE]:
                    route = record_route(kind, record)
                    if route in seen:
                        raise SiteError(
                            f"Duplicate frontend identity: {site.id}/{kind}/{route}"
                        )
                    seen.add(route)
                    raw_id = record.get(
                        _IDENTITY_FIELDS.get(kind, "header_id"),
                        record.get("area_id", record.get("map_index")),
                    )
                    relationship_key = (
                        record.get("slug")
                        if kind == "pokemon"
                        else str(encounter_route_key(record))
                        if kind == "encounters"
                        else str(raw_id)
                    )
                    chunk[route] = {
                        "record": record,
                        "relationships": relationships.get(kind, {}).get(
                            relationship_key, {}
                        ),
                    }
                    entry = _index_record(kind, record, route)
                    sprite = record.get("sprite")
                    if kind == "pokemon" and isinstance(sprite, dict):
                        entry["sprite"] = sprite.get("url")
                    related = relationships.get(kind, {}).get(relationship_key, {})
                    if kind == "pokemon":
                        entry["fields"]["availability_methods"] = sorted(
                            {
                                str(item.get("method", ""))
                                for domain in ("wild_encounters", "acquisition")
                                for item in related.get(domain, [])
                                if item.get("method")
                            }
                        )
                    if kind == "moves":
                        entry["fields"]["access_methods"] = [
                            label
                            for key, label in (
                                ("level_up_learners", "level-up"),
                                ("machine_learners", "machine"),
                            )
                            if related.get(key)
                        ] + [
                            key
                            for key in ("tutors", "egg_move_pokemon")
                            if record.get(key)
                        ]
                    if comparison is not None:
                        status_key = (
                            str(encounter_route_key(record))
                            if kind == "encounters" and record.get("source_type")
                            else str(raw_id)
                        )
                        entry["fields"]["change_status"] = [
                            statuses.get(status_key, "unchanged")
                        ]
                    entries.append(entry)
                resource = _write_resource(
                    output,
                    f"{site.id}/{kind}/chunk-{start // DETAIL_CHUNK_SIZE:04}",
                    chunk,
                )
                indexed.extend({**entry, "chunk": resource} for entry in entries)
            metadata = {
                key: value for key, value in dataset.items() if key != "records"
            }
            sections[kind] = {
                "index": _write_resource(
                    output, f"{site.id}/{kind}/index", {"records": indexed}
                ),
                "metadata": {
                    key: value
                    for key, value in metadata.items()
                    if key
                    in {
                        "record_count",
                        "features",
                        "schema_version",
                        "encounter_format",
                        "location_format",
                    }
                }
                # record_count counts every normalized record, including
                # placeholders the index omits; visitors see the index.
                | {"published_count": len(indexed)},
                "metadata_path": _write_resource(
                    output, f"{site.id}/{kind}/metadata", metadata
                ),
            }
        download_root = output / site.id / "downloads"
        download_root.mkdir(parents=True, exist_ok=True)
        source_data = site.config_path.parent / "wiki/data"
        downloads = json.loads(
            (source_data / "manifest.json").read_text(encoding="utf-8")
        )
        for entry in downloads["files"]:
            shutil.copyfile(source_data / entry["path"], download_root / entry["path"])
        documents = _documentation(root, site, output)
        search_index = _write_resource(output, f"{site.id}/guide-search", documents)
        games.append(
            {
                "id": site.id,
                "name": site.name,
                "description": site.description,
                "generation": site.game.generation,
                "theme": site.theme,
                "versions": list(site.game.versions),
                "sections": sections,
                "comparisons": comparisons,
                "downloads": downloads["files"],
                "documents": [
                    {key: value for key, value in document.items() if key != "search"}
                    for document in documents
                ],
                "search_index": search_index,
            }
        )
    manifest = {"schema_version": FRONTEND_SCHEMA_VERSION, "games": games}
    write_json_atomic(output / "manifest.json", manifest)
    return len(games)

"""Publish the ROM-free, versioned data contract consumed by the React app."""

from __future__ import annotations

import gzip
import hashlib
import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from romwiki.pipeline.build.checks import check_game_datasets
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
# Stores one published file: `(path relative to the bundle, bytes)`.
PutFile = Callable[[str, bytes], None]
DETAIL_CHUNK_SIZE = 50
_SNIPPET = re.compile(r'^--8<--\s+"([^"]+)"\s*$', re.MULTILINE)
_FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)
_FRONTMATTER_TITLE = re.compile(r"^title:\s*(.+?)\s*$", re.MULTILINE)
_PLACEHOLDER_NAME = re.compile(r"[－\-\s]+")
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
            name = pokemon.get("name") if isinstance(pokemon, dict) else None
            occupied = bool(name)
            if occupied:
                methods.setdefault(method, []).append(str(name))
            for key, entry in value.items():
                # Empty slots keep a level of 0, which no encounter uses.
                if key in {"minimum_level", "maximum_level", "level"}:
                    if occupied and isinstance(entry, int) and entry > 0:
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


def _with_record_slugs(
    value: Any,
    item_slugs: Mapping[int, str],
    species_slugs: Mapping[int, str],
    key: str = "",
) -> Any:
    """Give references that only carry a ROM item or species ID their page slug."""
    if isinstance(value, list):
        return [
            _with_record_slugs(entry, item_slugs, species_slugs, key) for entry in value
        ]
    if not isinstance(value, dict):
        return value
    result = {
        field: _with_record_slugs(entry, item_slugs, species_slugs, field)
        for field, entry in value.items()
    }
    if "slug" in value:
        return result
    item_id = value.get("item_id")
    if isinstance(item_id, int) and item_id in item_slugs and "item_slug" not in value:
        result["item_slug"] = item_slugs[item_id]
    species_id = value.get("species_id")
    if (
        isinstance(species_id, int)
        and species_id in species_slugs
        and "pokemon_slug" not in value
    ):
        result["pokemon_slug"] = species_slugs[species_id]
    # A bare {id, name} under a "pokemon" key, such as an in-game trade's.
    pokemon_id = value.get("id")
    if key == "pokemon" and isinstance(pokemon_id, int) and pokemon_id in species_slugs:
        result["slug"] = species_slugs[pokemon_id]
    return result


def _mascot(
    owner: str, slug: str | None, datasets: list[dict[str, Any]]
) -> dict[str, str] | None:
    """The Pokémon that represents a site, with its sprite.

    A game's mascot comes from its own Pokémon; the portal's from the first
    game that publishes a sprite for it.
    """
    if slug is None:
        return None
    for dataset in datasets:
        for record in dataset.get("records", []):
            if record.get("slug") == slug:
                sprite = _index_sprite("pokemon", record)
                if sprite:
                    return {"name": str(record.get("name")), "sprite": sprite}
    raise SiteError(f"{owner} mascot has no published sprite: {slug}")


def _index_sprite(kind: str, record: Mapping[str, Any]) -> str | None:
    """The small image the app shows beside a Pokémon or item link."""
    if kind == "pokemon":
        sprite = record.get("sprite")
        url = sprite.get("url") if isinstance(sprite, Mapping) else None
    elif kind == "items":
        reference = record.get("reference")
        url = reference.get("sprite_url") if isinstance(reference, Mapping) else None
    else:
        return None
    return url if isinstance(url, str) else None


def _index_record(kind: str, record: dict[str, Any], route: str) -> dict[str, Any]:
    label = str(record.get("name") or route)
    # Unused map headers keep the ROM's placeholder name, a row of dashes.
    if _PLACEHOLDER_NAME.fullmatch(label):
        label = f"Unnamed area ({route})"
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


@dataclass(frozen=True, slots=True)
class FrontendDocument:
    slug: str
    label: str
    markdown: str


@dataclass(frozen=True, slots=True)
class FrontendGame:
    """Everything the app needs to publish one game, independent of where the
    data came from: a repository build or a ROM processed in memory.
    """

    id: str
    name: str
    description: str
    generation: int
    theme: str
    mascot: str | None
    versions: tuple[str, ...]
    datasets: Mapping[str, dict[str, Any]]
    # Comparison with the base game by section; a game that is not its own
    # base game must have one for every section but `types`.
    comparisons: Mapping[str, dict[str, Any]]
    requires_comparisons: bool
    # The bulk-download manifest's `files` entries and each file's bytes.
    download_entries: Sequence[dict[str, Any]]
    download_files: Mapping[str, bytes]
    documents: Sequence[FrontendDocument] = field(default=())


def directory_files(output: Path) -> PutFile:
    """A `PutFile` that writes below `output`."""

    def put(relative: str, payload: bytes) -> None:
        path = output / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)

    return put


def _write_resource(put: PutFile, prefix: str, value: Any) -> str:
    payload = (
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        + b"\n"
    )
    digest = hashlib.sha256(payload).hexdigest()[:16]
    relative = f"{prefix}-{digest}.json"
    put(relative, payload)
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


def read_site_documents(root: Path, site: SiteDefinition) -> list[FrontendDocument]:
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
    # The game's own guides come first, led by their folder's index page;
    # the wiki's notes about its sources follow them.
    paths = sorted(
        (wiki / "docs").rglob("*.md"), key=lambda path: (path.stem != "index", path)
    ) + sorted(wiki.glob("*.md"))
    for path in paths:
        relative = path.relative_to(wiki).as_posix()
        slug = relative.removesuffix(".md")
        text = expand(path.read_text(encoding="utf-8"))
        frontmatter = _FRONTMATTER.match(text)
        if frontmatter:
            text = text[frontmatter.end() :]
        label = _document_label(path, frontmatter[1] if frontmatter else "", text)
        documents.append(FrontendDocument(slug=slug, label=label, markdown=text))
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
    for slug, chain in _evolution_chains(
        datasets.get("pokemon", {}).get("records", [])
    ).items():
        result["pokemon"].setdefault(slug, {})["evolution_chain"] = chain
    return result


def _evolution_chains(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Map each Pokémon slug to its whole evolution family as a tree.

    Records list only the evolutions leaving them, so a stage's page cannot
    otherwise show what it evolved from or where sibling branches lead.
    Alternate forms share their base form's family.
    """
    public = [
        record
        for record in records
        if record.get("public", True) and isinstance(record.get("slug"), str)
    ]
    by_slug = {record["slug"]: record for record in public}
    base_forms = {
        record["national_dex_id"]: record["slug"]
        for record in public
        if record.get("member") == record.get("national_dex_id")
    }

    def evolutions(record: dict[str, Any]) -> list[tuple[dict[str, Any], str]]:
        return [
            (evolution, target)
            for evolution in record.get("evolutions") or []
            if isinstance(target := (evolution.get("target") or {}).get("slug"), str)
            and target in by_slug
        ]

    parents: dict[str, str] = {}
    for record in public:
        for _, target in evolutions(record):
            parents.setdefault(target, record["slug"])

    def node(slug: str, seen: frozenset[str]) -> dict[str, Any]:
        record = by_slug[slug]
        steps = []
        for evolution, target in evolutions(record):
            if target not in seen:
                steps.append(
                    {
                        **{
                            key: evolution.get(key)
                            for key in ("method", "parameter", "parameter_data")
                        },
                        "target": node(target, seen | {target}),
                    }
                )
        return {
            "name": record.get("name"),
            "slug": slug,
            "national_dex_id": record.get("national_dex_id"),
            "evolutions": steps,
        }

    chains: dict[str, dict[str, Any]] = {}
    for record in public:
        slug: str = base_forms.get(record.get("national_dex_id"), record["slug"])
        root, seen = slug, {slug}
        while root in parents and parents[root] not in seen:
            root = parents[root]
            seen.add(root)
        chain = node(root, frozenset({root}))
        if chain["evolutions"]:
            chains[record["slug"]] = chain
    return chains


def export_frontend(root: Path, output: Path, *, data_root: Path | None = None) -> int:
    """Write a content-addressed frontend bundle, rejecting incomplete comparisons.

    Existing normalized downloads remain independently versioned. Comparison
    inputs are supplied by local builds or restored data snapshots, never HTML.
    """
    root, output = root.resolve(), output.resolve()
    _check_output(root, output)
    catalog = SiteCatalog.load(root)
    put = directory_files(output)
    games = []
    pokemon: list[dict[str, Any]] = []
    for site in catalog.published():
        if site.game is None:
            continue
        game = _site_game(root, site, data_root)
        pokemon.append(game.datasets.get("pokemon", {}))
        games.append(render_game(game, put))
    portal = next(site for site in catalog.published() if site.kind == "portal")
    manifest = {
        "schema_version": FRONTEND_SCHEMA_VERSION,
        "mascot": _mascot(portal.id, portal.mascot, pokemon),
        "games": games,
    }
    write_json_atomic(output / "manifest.json", manifest)
    _remove_unreferenced(output)
    return len(games)


def _site_game(
    root: Path, site: SiteDefinition, data_root: Path | None
) -> FrontendGame:
    """A published site's game, read from its generated data in the checkout."""
    assert site.game is not None
    datasets = _read_datasets(site)
    profile_id = site.game.profiles[0] if len(site.game.profiles) == 1 else site.id
    comparison_dir = site.config_path.parent / "wiki/data/comparisons"
    if data_root is not None:
        comparison_dir = data_root / profile_id / "comparisons"
    comparisons = {
        kind: json.loads(path.read_text(encoding="utf-8"))
        for kind in datasets
        if (path := comparison_dir / f"{kind}.json").is_file()
    }
    source_data = site.config_path.parent / "wiki/data"
    downloads = json.loads((source_data / "manifest.json").read_text(encoding="utf-8"))
    return FrontendGame(
        id=site.id,
        name=site.name,
        description=site.description,
        generation=site.game.generation,
        theme=site.theme,
        mascot=site.mascot,
        versions=tuple(site.game.versions),
        datasets=datasets,
        comparisons=comparisons,
        requires_comparisons=site.id != site.game.base_game,
        download_entries=downloads["files"],
        download_files={
            entry["path"]: (source_data / entry["path"]).read_bytes()
            for entry in downloads["files"]
        },
        documents=read_site_documents(root, site),
    )


def render_game(game: FrontendGame, put: PutFile) -> dict[str, Any]:
    """Write one game's resources through `put` and return its manifest entry."""
    datasets = game.datasets
    check_game_datasets(game.id, datasets)
    relationships = _relationships(dict(datasets))
    # A species ID is its base form's member number; alternate forms
    # follow the national Pokédex in the personal archive.
    species_slugs = {
        record["member"]: record["slug"]
        for record in datasets.get("pokemon", {}).get("records", [])
        if record.get("public", True)
        and record.get("member") == record.get("national_dex_id")
        and isinstance(record.get("slug"), str)
    }
    item_slugs = {
        record["item_id"]: record["slug"]
        for record in datasets.get("items", {}).get("records", [])
        if record.get("public", True)
        and isinstance(record.get("item_id"), int)
        and isinstance(record.get("slug"), str)
    }
    sections: dict[str, Any] = {}
    comparisons: dict[str, str] = {}
    for kind, dataset in sorted(datasets.items()):
        comparison = game.comparisons.get(kind)
        if comparison is not None:
            if comparison.get("game") != dataset.get("game"):
                raise SiteError(
                    f"{game.id} {kind} comparison belongs to a different game"
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
                put, f"{game.id}/changes/{kind}", comparison
            )
        elif game.requires_comparisons and kind != "types":
            raise SiteError(
                f"Missing {game.id} {kind} comparison; regenerate or restore a complete data snapshot"
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
                and is_unlinked_encounter_area(record, dataset.get("encounter_format"))
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
                        f"Duplicate frontend identity: {game.id}/{kind}/{route}"
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
                chunk[route] = _with_record_slugs(
                    {
                        "record": record,
                        "relationships": relationships.get(kind, {}).get(
                            relationship_key, {}
                        ),
                    },
                    item_slugs,
                    species_slugs,
                )
                entry = _index_record(kind, record, route)
                sprite = _index_sprite(kind, record)
                if sprite:
                    entry["sprite"] = sprite
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
                        key for key in ("tutors", "egg_move_pokemon") if record.get(key)
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
                put,
                f"{game.id}/{kind}/chunk-{start // DETAIL_CHUNK_SIZE:04}",
                chunk,
            )
            indexed.extend({**entry, "chunk": resource} for entry in entries)
        metadata = {key: value for key, value in dataset.items() if key != "records"}
        sections[kind] = {
            "index": _write_resource(
                put, f"{game.id}/{kind}/index", {"records": indexed}
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
                put, f"{game.id}/{kind}/metadata", metadata
            ),
        }
    for entry in game.download_entries:
        put(f"{game.id}/downloads/{entry['path']}", game.download_files[entry["path"]])
    documents = [
        {
            "id": document.slug,
            "label": document.label,
            "path": _write_resource(
                put,
                f"{game.id}/docs/{document.slug}",
                {"markdown": document.markdown},
            ),
            "search": _search_text(document.markdown),
        }
        for document in game.documents
    ]
    search_index = _write_resource(put, f"{game.id}/guide-search", documents)
    return {
        "id": game.id,
        "name": game.name,
        "description": game.description,
        "generation": game.generation,
        "theme": game.theme,
        "mascot": _mascot(game.id, game.mascot, [datasets.get("pokemon", {})]),
        "versions": list(game.versions),
        "sections": sections,
        "comparisons": comparisons,
        "downloads": list(game.download_entries),
        "documents": [
            {key: value for key, value in document.items() if key != "search"}
            for document in documents
        ],
        "search_index": search_index,
    }


def _check_output(root: Path, output: Path) -> None:
    if output == root or root.is_relative_to(output):
        raise SiteError("Frontend output must not contain the repository")
    # Files the new manifest doesn't reference are deleted afterwards, so only
    # write into an empty directory or an earlier export.
    if (
        output.is_dir()
        and any(output.iterdir())
        and not (output / "manifest.json").is_file()
    ):
        raise SiteError(f"Frontend output is not an earlier export: {output}")


def _remove_unreferenced(output: Path) -> None:
    """Delete resources earlier exports wrote that this manifest dropped."""
    referenced = {path.resolve() for path in publication_files(output)}
    for path in sorted(output.rglob("*"), reverse=True):
        if path.is_file() and path.resolve() not in referenced:
            path.unlink()
        elif path.is_dir() and not any(path.iterdir()):
            path.rmdir()


def publication_files(root: Path) -> list[Path]:
    """Every file the frontend manifest at `root` references, checked to exist."""
    # Resolve once the directory exists: on Windows, a path resolved before its
    # directory was created can keep an 8.3 short name its files won't share.
    root = root.resolve()
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != FRONTEND_SCHEMA_VERSION:
        raise SiteError("Unsupported frontend publication schema")
    files = {manifest_path}
    included: dict[str, Path] = {}

    def include(relative: str) -> Path:
        if relative in included:
            return included[relative]
        candidate = (root / relative).resolve()
        if not candidate.is_relative_to(root) or not candidate.is_file():
            raise SiteError(f"Invalid frontend resource: {relative}")
        files.add(candidate)
        included[relative] = candidate
        return candidate

    for game in manifest["games"]:
        for section in game["sections"].values():
            include(section["metadata_path"])
            index = json.loads(include(section["index"]).read_text(encoding="utf-8"))
            for row in index["records"]:
                include(row["chunk"])
        for comparison in game["comparisons"].values():
            include(comparison)
        for document in game["documents"]:
            include(document["path"])
        include(game["search_index"])
        for download in game["downloads"]:
            path = include(f"{game['id']}/downloads/{download['path']}")
            if hashlib.sha256(path.read_bytes()).hexdigest() != download["sha256"]:
                raise SiteError(f"Frontend download checksum mismatch: {path}")
    return sorted(files, key=lambda path: path.relative_to(root).as_posix())

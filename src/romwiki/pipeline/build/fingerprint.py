from __future__ import annotations

import ast
import hashlib
import json
from collections.abc import Iterable
from dataclasses import asdict, fields, is_dataclass
from functools import cache
from pathlib import Path
from types import ModuleType
from typing import Any

_FINGERPRINT_FORMAT_VERSION = 1
_PACKAGE_ROOT = Path(__file__).resolve().parents[2]
_SOURCE_ROOT = _PACKAGE_ROOT.parent
GENERATION_EXTRACTOR_MODULES = (
    "romwiki.pipeline.extraction.personal",
    "romwiki.pipeline.extraction.learnsets",
    "romwiki.pipeline.extraction.egg_moves",
    "romwiki.pipeline.extraction.evolutions",
    "romwiki.pipeline.extraction.machines",
    "romwiki.pipeline.extraction.tutors",
    "romwiki.pipeline.extraction.pickup",
    "romwiki.pipeline.extraction.moves",
    "romwiki.pipeline.extraction.encounters",
    "romwiki.pipeline.extraction.trainers.dispatcher",
    "romwiki.pipeline.extraction.locations.dispatcher",
    "romwiki.pipeline.extraction.items",
    "romwiki.pipeline.extraction.trades",
    "romwiki.pipeline.extraction.marts",
    "romwiki.pipeline.extraction.static_encounters",
)


@cache
def combined_extraction_source_fingerprint(
    engine_id: str,
    extractor_modules: tuple[str, ...],
    cache_key: str,
) -> str:
    """Hash the local code used by an extraction path that also embeds one or
    more other extractors' output as data rather than importing it (e.g.
    locations embedding trainers/items/static-encounters/marts/trades) --
    invalidated by a change to any of those extractors too, not just the
    primary one's own import closure."""
    digest = hashlib.sha256()
    digest.update(f"v{_FINGERPRINT_FORMAT_VERSION}\0{cache_key}\0".encode())
    digest.update(_engine_descriptor(engine_id))
    digest.update(b"\0")
    relative_paths: set[str] = set()
    for extractor_module in extractor_modules:
        relative_paths.update(extraction_source_files(engine_id, extractor_module))
    for relative_path in sorted(relative_paths):
        path = _PACKAGE_ROOT / relative_path
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


@cache
def extraction_source_files(engine_id: str, extractor_module: str) -> tuple[str, ...]:
    """Return the local Python dependency closure for an extraction path."""
    pending = [extractor_module, *_engine_source_modules(engine_id)]
    visited: set[str] = set()
    paths: set[Path] = set()

    while pending:
        module_name = pending.pop()
        if module_name in visited:
            continue
        visited.add(module_name)
        path = _module_path(module_name)
        if path is None:
            continue
        if module_name == "romwiki.engines.registry":
            # Registration for unrelated engines must not invalidate this
            # engine. Its resolved adapter metadata is hashed separately.
            continue
        paths.add(path)
        for dependency in _local_imports(path, module_name):
            pending.append(dependency)

    return tuple(sorted(path.relative_to(_PACKAGE_ROOT).as_posix() for path in paths))


def profile_fingerprint(profile: Any) -> str:
    """Hash the resolved profile values that control extraction."""
    value = (
        asdict(profile)
        if is_dataclass(profile) and not isinstance(profile, type)
        else {"id": profile.id}
    )
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _engine_source_modules(engine_id: str) -> tuple[str, ...]:
    from romwiki.engines.registry import get_engine

    modules: set[str] = set()

    def collect(value: Any) -> None:
        if isinstance(value, ModuleType):
            modules.add(value.__name__)
            return
        primary = getattr(value, "primary", None)
        fallback = getattr(value, "fallback", None)
        if primary is not None and fallback is not None:
            collect(primary)
            collect(fallback)

    adapter = get_engine(engine_id)
    for field in fields(adapter):
        collect(getattr(adapter, field.name))
    return tuple(sorted(modules))


def _engine_descriptor(engine_id: str) -> bytes:
    from romwiki.engines.registry import get_engine

    adapter = get_engine(engine_id)
    value = {
        "modules": _engine_source_modules(engine_id),
        "formats": asdict(adapter.formats),
        "generation": adapter.generation,
        "presentation_features": sorted(adapter.presentation_features),
        "capabilities": sorted(adapter.capabilities),
        "dataset_kinds": sorted(adapter.dataset_kinds),
        "required_dataset_kinds": sorted(adapter.required_dataset_kinds),
        "profile_contract": asdict(adapter.profile_contract),
    }
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    ).encode("utf-8")


def _json_default(value: Any) -> Any:
    if isinstance(value, (set, frozenset)):
        return sorted(value)
    raise TypeError(f"Cannot serialize {type(value).__name__}")


def _module_path(module_name: str) -> Path | None:
    if module_name == "romwiki":
        candidate = _PACKAGE_ROOT / "__init__.py"
        return candidate if candidate.is_file() else None
    if not module_name.startswith("romwiki."):
        return None
    relative = Path(*module_name.split("."))
    module_path = _SOURCE_ROOT / relative.with_suffix(".py")
    if module_path.is_file():
        return module_path
    package_path = _SOURCE_ROOT / relative / "__init__.py"
    return package_path if package_path.is_file() else None


def _local_imports(path: Path, module_name: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    dependencies: set[str] = set()
    package = (
        module_name if path.name == "__init__.py" else module_name.rpartition(".")[0]
    )

    for node in ast.walk(tree):
        candidates: Iterable[str | None]
        if isinstance(node, ast.Import):
            candidates = (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = _resolve_import_base(package, node.module, node.level)
            candidates = (base, *(f"{base}.{alias.name}" for alias in node.names))
        else:
            continue
        for candidate in candidates:
            if candidate and _module_path(candidate) is not None:
                dependencies.add(candidate)
    return dependencies


def _resolve_import_base(package: str, module: str | None, level: int) -> str:
    if not level:
        return module or ""
    parts = package.split(".") if package else []
    parts = parts[: len(parts) - level + 1]
    if module:
        parts.extend(module.split("."))
    return ".".join(parts)

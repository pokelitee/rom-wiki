from __future__ import annotations

import ast
import unittest
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src" / "romwiki"
ENGINE_ROOT = SOURCE_ROOT / "engines"
REGISTRY_PATH = ENGINE_ROOT / "registry.py"


class EnginePackageBoundaryTests(unittest.TestCase):
    def test_leaf_engines_do_not_depend_on_other_leaves_or_generations(self) -> None:
        leaves = _engine_leaves()
        violations = []
        for path in SOURCE_ROOT.rglob("*.py"):
            if path == REGISTRY_PATH:
                continue
            current_leaf = _containing_leaf(path, leaves)
            current_generation = current_leaf.split(".")[2] if current_leaf else None
            for imported in _imports(path):
                target_leaf = next(
                    (
                        leaf
                        for leaf in leaves
                        if imported == leaf or imported.startswith(f"{leaf}.")
                    ),
                    None,
                )
                if target_leaf is not None and target_leaf != current_leaf:
                    violations.append(
                        f"{path.relative_to(SOURCE_ROOT)} imports leaf {target_leaf}"
                    )
                    continue
                if (
                    current_generation is not None
                    and imported.startswith("romwiki.engines.gen")
                    and not imported.startswith(
                        f"romwiki.engines.{current_generation}."
                    )
                ):
                    violations.append(
                        f"{path.relative_to(SOURCE_ROOT)} imports another generation: "
                        f"{imported}"
                    )

        self.assertEqual(violations, [])


def _engine_leaves() -> tuple[str, ...]:
    return tuple(
        f"romwiki.engines.{generation.name}.{family.name}"
        for generation in ENGINE_ROOT.iterdir()
        if generation.is_dir() and generation.name.startswith("gen")
        for family in generation.iterdir()
        if family.is_dir() and (family / "__init__.py").is_file()
    )


def _containing_leaf(path: Path, leaves: tuple[str, ...]) -> str | None:
    module = _module_name(path)
    return next(
        (
            leaf
            for leaf in leaves
            if module == leaf or module.startswith(f"{leaf}.")
        ),
        None,
    )


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    module_parts = _module_name(path).split(".")
    package_parts = module_parts if path.name == "__init__.py" else module_parts[:-1]
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                keep = len(package_parts) - node.level + 1
                base_parts = package_parts[:keep]
                if node.module:
                    base_parts.extend(node.module.split("."))
                base = ".".join(base_parts)
            else:
                base = node.module or ""
            if base:
                imported.add(base)
                imported.update(f"{base}.{alias.name}" for alias in node.names)
    return imported


def _module_name(path: Path) -> str:
    relative = path.relative_to(SOURCE_ROOT.parent).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


if __name__ == "__main__":
    unittest.main()

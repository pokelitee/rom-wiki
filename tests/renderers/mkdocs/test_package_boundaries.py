from __future__ import annotations

import ast
import unittest
from pathlib import Path

RENDERER_ROOT = (
    Path(__file__).resolve().parents[3] / "src" / "romwiki" / "renderers" / "mkdocs"
)
RENDERER_PACKAGE = "romwiki.renderers.mkdocs."


class RendererPackageBoundaryTests(unittest.TestCase):
    def test_renderer_modules_do_not_import_private_sibling_names(self) -> None:
        violations = []
        for path in RENDERER_ROOT.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom):
                    continue
                imported_module = node.module or ""
                if not imported_module.startswith(RENDERER_PACKAGE):
                    continue
                for alias in node.names:
                    if alias.name.startswith("_"):
                        violations.append(
                            f"{path.name} imports {alias.name} from {imported_module}"
                        )

        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()

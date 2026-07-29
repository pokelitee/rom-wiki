from __future__ import annotations

import shlex
import unittest
from pathlib import Path

from romwiki.cli import build_parser

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class DocumentationTests(unittest.TestCase):
    def test_documented_cli_commands_parse(self) -> None:
        parser = build_parser()
        paths = [
            REPOSITORY_ROOT / "README.md",
            *(REPOSITORY_ROOT / "docs").rglob("*.md"),
        ]
        commands = []
        for path in paths:
            for line_number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(),
                start=1,
            ):
                if line.startswith("romwiki "):
                    commands.append((path, line_number, line))

        self.assertTrue(commands)
        for path, line_number, command in commands:
            with self.subTest(path=path, line=line_number):
                parser.parse_args(shlex.split(command, posix=False)[1:])


if __name__ == "__main__":
    unittest.main()

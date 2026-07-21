from __future__ import annotations

from pathlib import Path
import unittest

from romwiki.renderers.mkdocs.dev_fixtures import DEV_FIXTURE_PAGES


_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_MKDOCS_DEV_YML = (
    _REPOSITORY_ROOT / "sites" / "games" / "renegade-platinum" / "mkdocs.dev.yml"
)


def _kept_pages_from_exclude_docs(text: str) -> dict[str, set[str]]:
    """Parse the `!/section/slug.md` keep-entries out of `exclude_docs: |`.

    This is a small hand-rolled parser rather than a full YAML load so the
    test suite doesn't need PyYAML (an optional `docs`-extra dependency)
    just to check that two lists of page names agree.
    """
    lines = text.splitlines()
    start = next(
        index for index, line in enumerate(lines) if line.strip() == "exclude_docs: |"
    )
    kept: dict[str, set[str]] = {}
    for line in lines[start + 1 :]:
        if not line.startswith("  "):
            break
        entry = line.strip()
        if not entry.startswith("!/"):
            continue
        section, _, filename = entry[2:].partition("/")
        if filename == "index.md":
            continue
        kept.setdefault(section, set()).add(filename.removesuffix(".md"))
    return kept


class DevFixtureConsistencyTests(unittest.TestCase):
    def test_dev_fixture_pages_match_mkdocs_dev_yml_exclusions(self) -> None:
        text = _MKDOCS_DEV_YML.read_text(encoding="utf-8")

        kept = _kept_pages_from_exclude_docs(text)

        self.assertEqual(
            kept,
            {section: set(pages) for section, pages in DEV_FIXTURE_PAGES.items()},
        )


if __name__ == "__main__":
    unittest.main()

"""Representative-page fixtures used to speed up local development builds.

Each entry names the page(s) kept for a section when a build is limited to
"dev" mode (see the ``--dev`` build flag). This must stay in sync with the
``exclude_docs`` entries in ``sites/games/renegade-platinum/mkdocs.dev.yml``,
which excludes every other detail page from the MkDocs build itself;
``tests/test_dev_fixtures.py`` asserts the two lists match.
"""

from __future__ import annotations

DEV_FIXTURE_PAGES: dict[str, frozenset[str]] = {
    "pokemon": frozenset({"bulbasaur", "eevee", "wurmple"}),
    "abilities": frozenset({"overgrow"}),
    "items": frozenset({"master-ball"}),
    "moves": frozenset({"pound"}),
    "encounters": frozenset({"area-000"}),
    "trainers": frozenset({"trainer-0001"}),
    "locations": frozenset({"header-000"}),
}

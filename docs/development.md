# Development

See the [README](../README.md) for quick start and the [organization contribution guide](https://github.com/pokelitee/.github/blob/main/CONTRIBUTING.md) for shared PR policies. Run commands from the repository root.

## Environment and checks

Use Python 3.12+, Node 22.12+, and a virtual environment. Activate it with `.venv\Scripts\Activate.ps1` in PowerShell or `source .venv/bin/activate` in bash.

```sh
python -m venv .venv
# Activate the environment using your shell's command.
python -m pip install -r requirements/dev.txt
python -m pip install --no-deps --no-build-isolation -e .
python -m ruff format --check .
python -m ruff check .
python -m mypy src/romwiki tests
python -m mypy scripts
python -m pytest -q
python scripts/check_package.py
npm --prefix web ci
npm --prefix web run lint
npm --prefix web run typecheck
npm --prefix web test
npm --prefix web run build
```

CI runs these checks on Ubuntu and Windows with Python 3.12 and 3.13. Tests use synthetic inputs and fixtures rather than requiring local ROM images. Tests are type-checked against the real types they import, with the relaxations `pyproject.toml` explains for helpers and test doubles; scripts are checked on their own because they are standalone modules.

With local ROMs registered and `pokedb_root` set in `.local/games.toml`, also build every registered profile from its real ROM. This takes several minutes, so it only runs when enabled:

```sh
ROMWIKI_ROM_TESTS=1 python -m pytest tests/pipeline/build/test_engine_capability_contract.py tests/pipeline/build/test_rom_evidence.py tests/sites/test_web_build.py
```

The capability test requires every published game's data to pass the content checks in `pipeline/build/checks.py`. The evidence test keeps the facts profiles rely on checked against each ROM: Gen III tables sit where their code points, every reachable Gen III script decodes, the script specials find every trade and event Pokémon, and each Gen IV Pokédex bank matches its own version's text. The web build test checks that `romwiki.sites.web_build.build_wiki`, which builds one game's frontend bundle from a ROM in memory for the browser generator, publishes exactly what `site export-web` does for every single-ROM site, and that a ROM no profile knows builds as its retail game, marked unverified. It compares against the checkout's generated data, so regenerate first after a pipeline change. Generation and `site export-web` apply the same checks and refuse to write or publish data that fails them. The package smoke check builds a source distribution and wheel, installs the wheel in an isolated environment, and checks the CLI outside the checkout.

The installed CLI is distributed as a Python package; profiles, site configuration, authored content, and snapshots belong to the repository checkout. Wiki generation must run with those repository resources available. A wheel alone is not a bundled copy of the published wiki corpus.

## Generated files

Some committed files are generated rather than written by hand, by the scripts in
`scripts/generate/`. Each writes its output, or with `--check` fails if the
committed file is stale. Rerun one after changing its inputs and review the diff.
None runs in CI, because each needs inputs CI doesn't have:

```sh
python scripts/generate/gen3_script_commands.py --check   # pret sources
python scripts/generate/profile_symbols.py --check        # pret symbols + retail ROMs
python scripts/generate/gen3_compound_names.py --check    # PokéDB
```

- `gen3_script_commands.py` writes the Gen III event-script command tables
  (`engines/gen3/shared/script_command_table.py`) from pret's macro and command
  table sources.
- `profile_symbols.py` writes `profiles/symbols/<table>.toml`: the offset and size
  of each pret symbol a profile names, and the `gSpecials` index of each named
  special. For Generation III it also records each table's pointer sites, found
  by scanning the retail ROMs configured in `.local/games.toml`.
- `gen3_compound_names.py` writes the casing of run-together Generation III names
  (`engines/gen3/shared/compound_names.py`) from PokéDB's Generation III move,
  ability, and item slugs, found through `pokedb_root` in `.local/games.toml`.

`scripts/generate/pret_sources.toml` pins the pret commit each pret-based
generator reads; downloads are cached under `.romwiki/pret-cache/`, so only the
first run after a pin change needs network access. Generated files name their
generator and source commit in their header.

## Architecture and reference guides

Platform readers open containers, engines decode records, and pipelines normalize, enrich, compare, and publish data. Keep ROM offsets and engine encodings out of published data consumers.

- [Architecture](development/architecture.md): repository layout, orchestration, caches, and ownership boundaries.
- [Adding a game](development/adding-a-game.md): profiles, engines, tests, and publication checklist.
- [Data contracts](development/data-contracts.md): normalized and published JSON guarantees.
- [Frontend](development/frontend.md): React architecture, local preview, snapshots, and browser checks.
- [Open items](development/open-items.md): what the wikis do not cover yet, grouped by what blocks it.
- [CLI reference](cli-reference.md): commands and arguments.
- [Operations](operations.md): local inputs, generation, snapshots, publishing, and recovery.

Keep game-specific provenance and limitations in `sites/games/<site-id>/wiki/data-sources.md`. Shared publication prose belongs in `sites/shared/partials/`. The deeper reference guides remain separate because they cover different maintainers' tasks.

## Dependencies and contract changes

`pyproject.toml` declares supported package extras. `requirements/dev.txt` pins the complete development environment: packaging, test, typing, analysis, and package-verification tools. CI uses these exact versions. Update the pins together, keep transitive dependencies consistent, and run checks before merging. Dependabot opens grouped weekly Python, npm, and GitHub Actions updates. Routine frontend version updates are limited to minor and patch releases; toolchain major upgrades require a separate compatibility review. Security updates remain eligible regardless of that version-update filter.

Update schema definitions, tests, and the data-contract guide together when changing normalized or published fields. Use synthetic ROM fixtures for parser regressions. Complete generation needs local inputs; report when verification was limited to offline tests or restored publication snapshots.

## Contributing and repository settings

Use short-lived branches and PRs into `main`; there is no permanent `dev` branch. The existing development history was integrated through a PR and its previous head is preserved at `archive/dev-2026-10-13`. Merged PR branches are deleted automatically. The stable required check is `CI gate`, backed by the full reusable test matrix and a complete publication build from the pinned frontend snapshot.

Rulesets are tracked in `.github/rulesets/`: main requires PRs, passing CI, and resolved review conversations, without administrator bypass; archived development tags cannot be updated or deleted. No approving review is required while there is one maintainer. Editing the JSON files does not apply GitHub settings.

The repository is public, and both tracked rulesets ("Protect main" and "Preserve archived development tags") are applied with active enforcement. After changing `main.json` or `tags.json`, apply the update through the ruleset API and read back the live settings; editing the files alone does not change GitHub.

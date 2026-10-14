# Development

See the [README](../README.md) for quick start and the [organization contribution guide](https://github.com/pokelitee/.github/blob/main/CONTRIBUTING.md) for shared PR policies. Run commands from the repository root.

## Environment and checks

Use Python 3.12+ and a virtual environment. Activate it with `.venv\Scripts\Activate.ps1` in PowerShell or `source .venv/bin/activate` in bash.

```sh
python -m venv .venv
# Activate the environment using your shell's command.
python -m pip install -r requirements/dev.txt
python -m pip install --no-deps --no-build-isolation -e .
python -m ruff format --check .
python -m ruff check .
python -m mypy src/romwiki
python -m pytest -q
python scripts/check_package.py
```

CI runs these checks on Ubuntu and Windows with Python 3.12 and 3.13. Tests use synthetic inputs and fixtures rather than requiring local ROM images. One Ubuntu job also downloads, restores, and validates every publication snapshot, catching stale source fingerprints and unpublished snapshot assets before merge. The package smoke check builds a source distribution and wheel, installs the wheel in an isolated environment, and checks the CLI outside the checkout.

The installed CLI is distributed as a Python package; profiles, site configuration, templates, and snapshots belong to the repository checkout. Wiki generation must run with those repository resources available. A wheel alone is not a bundled copy of the published wiki corpus.

## Architecture and reference guides

Platform readers open containers, engines decode records, pipelines normalize/enrich/compare data, and renderers consume normalized records. Keep ROM offsets and engine encodings out of rendering code.

- [Architecture](development/architecture.md): repository layout, orchestration, caches, and ownership boundaries.
- [Adding a game](development/adding-a-game.md): profiles, engines, tests, and publication checklist.
- [Data contracts](development/data-contracts.md): normalized and published JSON guarantees.
- [Frontend](development/frontend.md): shared MkDocs templates, styling, and preview behavior.
- [Open items](development/open-items.md): unresolved selector research and known limitations.
- [CLI reference](cli-reference.md): commands and arguments.
- [Operations](operations.md): local inputs, generation, snapshots, deployment, and recovery.

Keep game-specific provenance and limitations in `sites/games/<site-id>/wiki/data-sources.md`. Shared publication prose belongs in `sites/shared/partials/`; frontend templates and assets belong in `sites/shared/overrides/`. The deeper reference guides remain separate because they cover different maintainers' tasks.

## Dependencies and contract changes

`pyproject.toml` declares supported package extras. `requirements/docs.txt` pins documentation/build dependencies; `requirements/dev.txt` includes those pins plus test, typing, analysis, and package-verification tools. CI and deployment use these exact versions. Update the pins together, keep transitive dependencies consistent, and run checks before merging. Dependabot opens grouped weekly Python and GitHub Actions updates.

Update schema definitions, tests, and the data-contract guide together when changing normalized or published fields. Use synthetic ROM fixtures for parser regressions. Complete generation needs local inputs; report when verification was limited to offline tests or restored publication snapshots.

## Contributing and repository settings

Use short-lived branches and PRs into `main`; there is no permanent `dev` branch. The existing development history was integrated through a PR and its previous head is preserved at `archive/dev-2026-10-13`. Merged PR branches are deleted automatically. The stable required check is `CI gate`, backed by the full reusable test matrix.

Rulesets are tracked in `.github/rulesets/`: main requires PRs, passing CI, and resolved review conversations, without administrator bypass; archived development tags cannot be updated or deleted. No approving review is required while there is one maintainer. Editing the JSON files does not apply GitHub settings.

The repository is public, and both tracked rulesets ("Protect main" and "Preserve archived development tags") are applied with active enforcement. After changing `main.json` or `tags.json`, apply the update through the ruleset API and read back the live settings; editing the files alone does not change GitHub.

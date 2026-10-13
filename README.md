# ROM Wiki

ROM Wiki extracts structured Pokémon data from locally supplied ROM images and produces normalized datasets and static MkDocs wikis.

## Live wikis

Browse [pokelitee.github.io/rom-wiki](https://pokelitee.github.io/rom-wiki/). Each game's data-sources page records its input revisions, provenance, supported mechanics, and limitations. Data-driven publication does not imply exhaustive extraction.

## Getting started

Use Python 3.12+. Activate the environment with `.venv\Scripts\Activate.ps1` in PowerShell or `source .venv/bin/activate` in bash.

```sh
git clone https://github.com/pokelitee/rom-wiki.git
cd rom-wiki
python -m venv .venv
# Activate the environment using your shell's command.
python -m pip install -r requirements/docs.txt
python -m pip install --no-deps --no-build-isolation -e .
romwiki site restore-snapshot
romwiki site build --all --dev
romwiki site serve --all --dev
```

This previews the tracked ROM-free snapshots without extracting games. To generate new datasets, supply local inputs through the ignored `.local/games.toml` registry and follow [Operations](docs/operations.md). PokéDB reference data defaults to the sibling checkout's `.output/gen<N>` directory.

## Architecture

`src/romwiki/` separates platform readers, generation-specific engines, normalized schemas, pipelines, renderers, and site tooling. `profiles/` contains committed decoding configuration; `sites/` owns authored content, shared presentation, and reviewed publication snapshots. Tests mirror those layers.

## Documentation

- [Development](docs/development.md): setup, checks, architecture references, dependencies, and repository policy.
- [Operations](docs/operations.md): local inputs, generation, snapshots, deployment, and recovery.
- [CLI reference](docs/cli-reference.md): command arguments, input selection, and output options.
- [Data contracts](docs/development/data-contracts.md): normalized and published JSON guarantees.

## Contributing

Follow the [organization contribution guide](https://github.com/pokelitee/.github/blob/main/CONTRIBUTING.md) and the [development guide](docs/development.md). Use a short-lived branch and a PR into `main`.

## License and local inputs

Source code is licensed under the [MIT License](LICENSE). ROM images, patches, keys, saves, and extracted copyrighted assets are not committed. Users supply legally obtained inputs locally.

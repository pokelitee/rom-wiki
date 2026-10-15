# ROM Wiki

ROM Wiki extracts structured Pokémon data from locally supplied ROM images and publishes normalized datasets for one shared React reference app.

Browse the React reference site at [pokelitee.github.io/rom-wiki](https://pokelitee.github.io/rom-wiki/). Publishing uses the reviewed, manual GitHub Pages workflow.

## Development

Use Python 3.12+ and Node 22.12+. Activate a Python virtual environment, then run:

```sh
python -m pip install -r requirements/dev.txt
python -m pip install --no-deps --no-build-isolation -e .
python -m romwiki site export-web --data-root build/data
npm --prefix web ci
npm --prefix web run dev
```

Open `http://127.0.0.1:5173/rom-wiki/`. Export requires complete locally generated datasets and comparison outputs. Alternatively, download and restore the pinned complete frontend snapshot using the [frontend guide](docs/development/frontend.md). It includes comparison JSON; the older per-game release archives contain only normalized downloads.

Extraction uses the ignored `.local/games.toml` registry. See [Operations](docs/operations.md) for local inputs and generation. ROM inputs are never needed to restore a complete frontend snapshot or to run synthetic tests.

## Architecture

`src/romwiki/` owns platform readers, engines, normalized schemas, extraction, enrichment, comparisons, relationships, and data publication. `web/` owns routing and presentation through shared React/TypeScript components, Tailwind, and selected shadcn/ui controls. `sites/` owns game descriptors, authored Markdown, shared prose, and historical snapshot references; no MkDocs application or generated record bodies are tracked.

The app uses hash routes below `/rom-wiki/`, compact section indexes, and content-addressed detail chunks. Generated data and build artifacts are ignored. The previous MkDocs implementation remains available in Git history at `04b72f2`.

## Documentation

- [Development](docs/development.md): setup, checks, dependencies, and repository policy.
- [Architecture](docs/development/architecture.md): layer ownership and data flow.
- [Frontend](docs/development/frontend.md): React development, snapshots, and validation.
- [Operations](docs/operations.md): local inputs, generation, snapshots, and recovery.
- [CLI reference](docs/cli-reference.md): command arguments and output options.
- [Data contracts](docs/development/data-contracts.md): normalized and frontend publication guarantees.

## Contributing

Follow the [organization contribution guide](https://github.com/pokelitee/.github/blob/main/CONTRIBUTING.md) and the development guide. Use a short-lived branch and a PR into `main`.

## License and local inputs

Source code is licensed under the [MIT License](LICENSE). ROM images, patches, keys, saves, and extracted copyrighted assets are not committed. Users supply legally obtained inputs locally.

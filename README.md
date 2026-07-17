# ROM Wiki

ROM Wiki is an extensible Pokemon game-data extraction framework and static-wiki
generator. Initial development targets Pokemon Platinum and Renegade Platinum.

The project separates four concerns:

1. platform readers open game containers without interpreting Pokemon data;
2. engine adapters decode game-specific records;
3. normalized models combine ROM facts, PokéDB reference data, and annotations;
4. renderers generate MkDocs source from the normalized dataset.

## Current status

The current extraction slices identify Nintendo DS images, enumerate their
filesystem safely, read NARC archives, and decode normalized Gen IV Pokémon
personal data, wild encounters, map-linked location names, and trainer parties
with record-level provenance.

## Development setup

```console
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev,docs]"
```

Inspect a locally supplied game image:

```console
romwiki inspect ".local/roms/Pokemon - Platinum Version (USA).nds"
romwiki inspect ".local/roms/Pokemon - Platinum Version (USA).nds" --json
```

Write the machine-readable manifest used by later extraction stages:

```console
romwiki manifest ".local/roms/Pokemon - Platinum Version (USA).nds" --output build/data/manifest.json
```

Extract the first normalized Pokemon dataset:

```console
romwiki extract-personal ".local/roms/Pokemon - Platinum Version (USA).nds"
```

This writes `build/data/renegade-platinum/pokemon/personal.json`. Generated data is
ignored until its publication and review policy is finalized.

Build enriched records and the Pokémon wiki pages using the local PokéDB output:

```console
romwiki build-pokemon ".local/roms/Pokemon - Platinum Version (USA).nds"
```

This keeps the enriched audit dataset under `build/` and renders publishable
Markdown into `sites/games/renegade-platinum/wiki/pokemon/`.

Extract and render wild encounter tables:

```console
romwiki extract-encounters ".local/roms/Pokemon - Platinum Version (USA).nds"
romwiki build-encounters ".local/roms/Pokemon - Platinum Version (USA).nds"
```

Encounter pages use archive member IDs as stable file names while displaying the
in-game location names resolved through Platinum's map headers. Populated archive
members without a static map-header reference remain available in a separate
unreferenced section for auditing.

Extract and render trainer parties:

```console
romwiki extract-trainers ".local/roms/Pokemon - Platinum Version (USA).nds"
romwiki build-trainers ".local/roms/Pokemon - Platinum Version (USA).nds"
```

Trainer pages include battle type, levels, held items, and custom moves. Archive
member IDs provide stable page names even when several trainers share a name.

Profiles are loaded from `profiles/` by default. Use `--profiles-dir` to select a
different directory.

## Multi-site wiki

The repository publishes one umbrella Pages artifact while keeping each game as an
independent MkDocs site. The portal is emitted at the artifact root and game sites
are emitted under stable slugs such as `/renegade-platinum/`.

```text
sites/
├── portal/                    # Umbrella landing site
├── games/
│   └── renegade-platinum/     # Independent game site
└── shared/                    # Shared templates and assets
dist/                          # Ignored combined Pages artifact
```

List configured sites:

```console
romwiki site list
```

Build one game locally or every published site for deployment:

```console
romwiki site build renegade-platinum --output dist
romwiki site build --all --output dist
```

The GitHub Pages workflow builds only committed structured data and maintained wiki
content. It never requires or downloads a game image.

## PokéDB

PokéDB will be consumed as an external reference dataset rather than imported
through its internal implementation. The planned default local path is
`../pokedb/.output/gen4`, with a configurable remote data-branch fallback for CI.

## Legal notice

This repository does not include game images, patches, keys, or extracted
copyrighted assets. Users must supply legally obtained inputs locally. Common game
image and save-file extensions are ignored by Git.

# ROM Wiki

ROM Wiki is an extensible Pokemon game-data extraction framework and static-wiki
generator. Initial development targets Pokemon Platinum and Renegade Platinum.

The project separates four concerns:

1. platform readers open game containers without interpreting Pokemon data;
2. engine adapters decode game-specific records;
3. normalized models combine ROM facts, PokéDB reference data, and annotations;
4. renderers generate MkDocs source from the normalized dataset.

## Current status

The first development slice can identify Nintendo DS images, validate their basic
header and filesystem metadata, match known profiles by cryptographic hash, and
write a reproducible inspection manifest. Pokemon data parsers are the next
milestone.

## Development setup

```console
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev,docs]"
```

Inspect a locally supplied game image:

```console
romwiki inspect "Pokemon - Platinum Version (USA).nds"
romwiki inspect "Pokemon - Platinum Version (USA).nds" --json
```

Write the machine-readable manifest used by later extraction stages:

```console
romwiki manifest "Pokemon - Platinum Version (USA).nds" --output build/data/manifest.json
```

Profiles are loaded from `profiles/` by default. Use `--profiles-dir` to select a
different directory.

## PokéDB

PokéDB will be consumed as an external reference dataset rather than imported
through its internal implementation. The planned default local path is
`../pokedb/.output/gen4`, with a configurable remote data-branch fallback for CI.

## Legal notice

This repository does not include game images, patches, keys, or extracted
copyrighted assets. Users must supply legally obtained inputs locally. Common game
image and save-file extensions are ignored by Git.


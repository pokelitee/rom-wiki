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
personal data, move mechanics, wild encounters, map-linked location names, and
trainer parties with record-level provenance.

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

Extract exact level-up learnsets as a standalone audit dataset:

```console
romwiki extract-learnsets ".local/roms/Pokemon - Platinum Version (USA).nds"
```

This writes `build/data/renegade-platinum/pokemon/learnsets.json`. Each entry
preserves the level and move order stored for its species or form.

Extract exact evolution methods and parameters:

```console
romwiki extract-evolutions ".local/roms/Pokemon - Platinum Version (USA).nds"
```

This writes `build/data/renegade-platinum/pokemon/evolutions.json`, including
the ROM's internal item-name catalog used to resolve item-based conditions.

Extract exact TM/HM move assignments:

```console
romwiki extract-machines ".local/roms/Pokemon - Platinum Version (USA).nds"
```

This writes `build/data/renegade-platinum/machines/raw.json`. The Pokémon and
move builds join these assignments with the compatibility flags stored in each
Pokémon personal record.

Extract exact shard move-tutor assignments, costs, locations, and compatibility:

```console
romwiki extract-tutors ".local/roms/Pokemon - Platinum Version (USA).nds"
```

This writes `build/data/renegade-platinum/tutors/raw.json`. Platinum stores the
38 move records and 505 Pokémon/form compatibility rows in ARM9 overlay 5.

Build enriched records and the Pokémon wiki pages using the local PokéDB output:

```console
romwiki build-pokemon ".local/roms/Pokemon - Platinum Version (USA).nds"
```

The Pokémon build combines personal records, level-up learnsets, evolutions,
TM/HM compatibility, and shard move-tutor compatibility from the ROM, then uses
PokéDB to resolve stable Pokémon and move names and links.

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

Trainer pages include battle type, levels, held items, custom moves, and exact
map locations resolved from standard trainer objects and literal scripted battle
commands. Archive member IDs provide stable page names even when several trainers
share a name. Dynamically selected facility and rematch trainers, along with unused
records, remain in a separate unlinked section until their invocation paths can be
resolved without guessing.

Extract and render map locations and navigation:

```console
romwiki extract-locations ".local/roms/Pokemon - Platinum Version (USA).nds"
romwiki build-locations ".local/roms/Pokemon - Platinum Version (USA).nds"
```

Location pages combine map headers with exact event warps, outdoor map-matrix
connections, wild encounter tables, and trainer references. Each map header keeps
a stable page even when several interiors share the same displayed location name.

Extract and render move mechanics:

```console
romwiki extract-moves ".local/roms/Pokemon - Platinum Version (USA).nds"
romwiki build-moves ".local/roms/Pokemon - Platinum Version (USA).nds"
```

Move pages report the exact type, damage class, power, accuracy, PP, priority,
effect, targeting, flag, and contest fields stored in the hack's active move
archive. PokéDB supplies stable move names; mechanical values always come from
the game image.

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

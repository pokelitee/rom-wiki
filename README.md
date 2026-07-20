# ROM Wiki

ROM Wiki is an extensible Pokémon game-data extraction framework and static-wiki
generator. Initial development targets Pokémon Platinum and Renegade Platinum.

The project separates four concerns:

1. platform readers open game containers without interpreting Pokémon data;
2. engine adapters decode game-specific records;
3. normalized models combine ROM facts, PokéDB reference data, and annotations;
4. renderers generate MkDocs source from the normalized dataset.

## Current status

Renegade Platinum is the first complete baseline implementation. It identifies
Nintendo DS images, reads their filesystem and NARC archives, and generates
normalized datasets and wiki pages for Pokémon, moves, wild encounters,
trainers, and locations. The location dataset also includes items, shops,
warps, connections, gifts, static encounters, roaming activation audits, and
in-game trades. Extracted records retain ROM provenance where practical.

The project is designed to support additional games without coupling the wiki
renderer to a particular ROM format. The normalized data contracts and MkDocs
renderers are reusable, but extraction dispatch currently targets the
Nintendo DS `gen4_dppt` engine directly. Supporting a different platform or
generation therefore requires a new platform reader and/or engine adapter; it
is not only a profile change.

See [Architecture](docs/development/architecture.md) for the data flow and
current extension boundaries, and [Adding a game](docs/development/adding-a-game.md)
for the implementation checklist.

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

Extract the first normalized Pokémon dataset:

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

Extract exact egg move lists from the packed ARM9 table:

```console
romwiki extract-egg-moves ".local/roms/Pokemon - Platinum Version (USA).nds"
```

This writes `build/data/renegade-platinum/pokemon/egg-moves.json`. Each record
preserves the species marker, move order, table index, and overlay offset.

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

Extract exact move-tutor assignments, requirements, locations, and compatibility:

```console
romwiki extract-tutors ".local/roms/Pokemon - Platinum Version (USA).nds"
```

This writes `build/data/renegade-platinum/tutors/raw.json`. The 38 shard-tutor
records and 505 Pokémon/form compatibility rows come from ARM9 overlay 5. Four
additional scripted tutors—Draco Meteor, Blast Burn, Hydro Cannon, and Frenzy
Plant—are decoded from their field-script commands and eligibility checks.

Build enriched records and the Pokémon wiki pages using the local PokéDB output:

```console
romwiki build-pokemon ".local/roms/Pokemon - Platinum Version (USA).nds"
```

The Pokémon build combines personal records, wild held-item slots, level-up and
egg moves, evolutions, TM/HM compatibility, and move-tutor compatibility from the ROM, then uses
PokéDB to resolve stable Pokémon and move names and links.

This keeps the enriched audit dataset under `build/` and renders publishable
Markdown into `sites/games/renegade-platinum/wiki/pokemon/`. The same command also
derives the normalized ability catalog from ROM names and personal-data assignments,
then renders it under `sites/games/renegade-platinum/wiki/abilities/`.

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

Location pages combine map headers with exact visible and hidden item pickups;
common, specialty, decoration, weekday seal-shop, and Battle Frontier BP
inventories and prices; event warps; outdoor map-matrix connections; wild
encounter tables; literal Pokémon and egg gifts; in-game trades; scripted static
encounters; roaming activation audits; and trainer references. Each map
header keeps a stable page even when several interiors share the same displayed
location name.

Extract and render move mechanics:

```console
romwiki extract-moves ".local/roms/Pokemon - Platinum Version (USA).nds"
romwiki build-moves ".local/roms/Pokemon - Platinum Version (USA).nds"
```

Move pages report the exact type, damage class, power, accuracy, PP, priority,
effect, targeting, flag, and contest fields stored in the hack's active move
archive. Move and type names come from configured ROM message tables. PokéDB
provides canonical comparison names and fallback metadata; ROM-derived values
remain authoritative.

Extract and render the item catalog:

```console
romwiki extract-items ".local/roms/Pokemon - Platinum Version (USA).nds"
romwiki build-items ".local/roms/Pokemon - Platinum Version (USA).nds"
```

Item pages combine the ROM item-name table, the 34-byte item mechanics records,
and the ARM9 item-to-archive-member map. The enriched build links overworld and
hidden pickups, shops, wild and trainer held items, trainer rewards, gifts,
trades, and item-based evolutions.

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

Preview an individual site with live reload:

```console
python -m mkdocs serve --config-file sites/games/renegade-platinum/mkdocs.yml
```

The portal can be previewed by using `sites/portal/mkdocs.yml` instead. Each site
inherits the shared responsive theme, light and dark palettes, catalog interface,
and game selector from `sites/shared/`.

Large generated sections expose progressively rendered catalogs with search,
filters, sorting, and bookmarkable query parameters. A complete static link list
remains available when JavaScript is disabled or a catalog cannot be loaded.

The GitHub Pages workflow builds only committed structured data and maintained wiki
content. It never requires or downloads a game image.

## PokéDB

PokéDB will be consumed as an external reference dataset rather than imported
through its internal implementation. The planned default local path is
`../pokedb/.output/gen4`, with a configurable remote data-branch fallback for CI.

Pokémon pages may also reference the generation-specific sprite URL selected from
PokéDB. Sprites are loaded lazily from the upstream PokéAPI sprites repository;
ROM Wiki does not download, cache, or publish copies of those image files. Missing
or unreachable images degrade to a text placeholder.

## Legal notice

This repository does not include game images, patches, keys, or extracted
copyrighted assets. Users must supply legally obtained inputs locally. Common game
image and save-file extensions are ignored by Git.

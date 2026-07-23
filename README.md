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
warps, connections, gifts, static encounters, roaming activations,
in-game trades, honey tree encounter pools, Great Marsh/Trophy Garden daily
rotation pools, and Game Corner prize exchanges. Extracted records retain ROM
provenance where practical.

Honey trees and the Great Marsh/Trophy Garden dailies read from
`arc/encdata_ex.narc`, a second encounter archive separate from the wild
encounter tables, and only expose what the ROM stores as fixed data: species
pools, not which entry is active. Which honey tree slathering yields, which
four trees are a save file's guaranteed Rare trees, and which Great
Marsh/Trophy Garden pool entries are live today are all derived from save-file
state (trainer ID, a daily seed, or a save-persisted rotation), not ROM data,
so those selections are out of scope by the same policy that keeps Poké Radar
chains and dual-slot "today's" pick unrendered elsewhere in this project.

Each roaming-Pokémon activation is now resolved to its species: the
species-per-slot assignment is a compiled ARM9 constant (not a NARC table),
verified against every real scripted activation call across both ROMs
(Verity Cavern → Mesprit, Fullmoon Island → Cresselia, Eterna City →
Moltres/Zapdos). Roamer level is also a compiled constant, but its exact ARM9
bytes were not locatable without a symbol table or disassembler, so level is
intentionally left unrendered rather than guessed — a hack that rebalances
difficulty could plausibly have changed it. Renegade Platinum removes all
three scripted roaming activations that exist in the base game.

The Game Corner's Prize Exchange counter reads a fixed 19-entry {item, price}
table at a literal ARM9 code offset (`game_corner_prize_table_offset`), not a
NARC table — verified byte-for-byte against the decompilation for the retail
ROM, then located at the identical offset in Renegade Platinum, which patches
the same table in place with an entirely different, held-item-focused prize
list (e.g. Life Orb, Leftovers, Focus Sash) rather than vanilla Platinum's TMs.

Some Gen IV data categories are known but not yet extracted: the ROM's own
Pokédex/description text banks. This needs dedicated offset research and is
tracked as follow-up work rather than silently approximated.

The exact USA retail release of Pokémon Platinum is also registered as the
`platinum-us` profile. It reuses the Generation IV engine and has been validated
across every raw and enriched dataset as the clean normalized baseline for
Renegade Platinum comparisons. Comparative builds annotate every supported
catalog and detail page and generate a game-wide Changes overview.

The project is designed to support additional games without coupling the wiki
renderer to a particular ROM format. The normalized data contracts and MkDocs
renderers are reusable, and extraction dispatch resolves the platform and engine
adapter for a profile through the registries in `src/romwiki/platforms/registry.py`
and `src/romwiki/engines/registry.py` rather than importing the Nintendo DS
`gen4_dppt` engine directly. Supporting a different platform or generation still
requires writing a new platform reader and/or engine adapter and registering it;
it is not only a profile change, but no existing pipeline module needs to change
to add one.

See [Architecture](docs/development/architecture.md) for the data flow and
current extension boundaries, and [Adding a game](docs/development/adding-a-game.md)
for the implementation checklist.

## Development setup

```console
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev,docs]"
```

### Local game inputs

Keep machine-specific ROM paths in the ignored `.local/games.toml` registry rather
than committed profiles. Start from the tracked example:

```powershell
New-Item -ItemType Directory -Force .local | Out-Null
Copy-Item config/games.example.toml .local/games.toml
```

Paths are relative to the configuration file. A hack entry may declare both its
patched image and the clean base release used for normalized comparisons:

```toml
version = 1

[games.renegade-platinum]
patched_rom = "roms/Pokemon - Renegade Platinum.nds"
base_rom = "roms/Pokemon - Platinum Version (USA).nds"
```

Select the patched image by game ID, or add `--base` to select its clean base:

```console
romwiki inspect --game renegade-platinum
romwiki inspect --game renegade-platinum --base
romwiki build-game --game renegade-platinum
romwiki extract-personal --game renegade-platinum --base
```

`build-game` is the normal complete workflow. It finishes and caches all clean-ROM
raw extraction before parsing the hack, then builds Pokémon, abilities, moves,
items, encounters, trainers, locations, semantic comparison JSON, and the wiki.
Cached baseline data lives under `build/data/baselines/<base-profile>/` and is
reused while its profile, ROM hash, schema, and cache revision still match.

The same caching also applies to the hack ROM's raw extraction, cached under
`build/data/cache/<profile>/`. If the hack ROM's hash hasn't changed since the
last build, extraction is skipped and the cached data is reused; enrichment and
rendering still run, but this cuts out the slowest step of an unchanged rebuild.
Pass `--refresh-cache` to force re-extraction regardless.

```console
romwiki baseline build --game renegade-platinum
romwiki baseline build --game renegade-platinum --scope pokemon moves
romwiki build-game --game renegade-platinum --refresh-baseline
romwiki build-game --game renegade-platinum --refresh-cache
```

Configured builds require the registered base ROM by default. For an explicit ROM
path, supply `--base-rom`; use `--hack-only` only when intentionally generating a
site without comparisons:

```console
romwiki build-game --rom "D:\Games\hack.nds" --base-rom "D:\Games\base.nds"
romwiki build-moves --rom "D:\Games\hack.nds" --hack-only
```

The individual `build-*` commands remain useful during focused development and
follow the same baseline policy. `inspect`, `manifest`, and `extract-*` stay
single-ROM audit commands and never implicitly parse another image. MkDocs itself
only consumes generated files and never opens a ROM.

Use `--games-config` for a different registry. `--rom` provides a one-command
override, and the original positional path remains supported:

```console
romwiki inspect --rom "D:\Games\patched.nds"
romwiki inspect "D:\Games\patched.nds"
```

Only the selected path is validated for inspection and raw extraction. Comparative
builds validate both configured paths before building. Profiles remain responsible
for identifying each image; registering a path does not make an otherwise
unsupported base release extractable.

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
romwiki build-pokemon --game renegade-platinum
```

The Pokémon build combines personal records, wild held-item slots, level-up and
egg moves, evolutions, TM/HM compatibility, and move-tutor compatibility from the ROM, then uses
PokéDB to resolve stable Pokémon and move names and links.

This keeps the enriched audit dataset under `build/` and renders publishable
Markdown into `sites/games/renegade-platinum/wiki/pokemon/`. The same command also
derives the normalized ability catalog from ROM names and personal-data assignments,
then renders it under `sites/games/renegade-platinum/wiki/abilities/`. The extracted
ability data covers the name table and per-Pokémon assignments; the in-game
description text lives in separate message banks that ROM Wiki does not yet
extract, so ability pages carry PokéDB's effect description and flavor-text quote.

Extract and render wild encounter tables:

```console
romwiki extract-encounters ".local/roms/Pokemon - Platinum Version (USA).nds"
romwiki build-encounters ".local/roms/Pokemon - Platinum Version (USA).nds"
```

Encounter pages use archive member IDs as stable file names while displaying the
in-game location names resolved through Platinum's map headers. Populated archive
members without a static map-header reference remain available in a separate
unreferenced section for auditing. Each slot's catch chance is derived from the
fixed, publicly documented Generation III/IV per-slot weight tables (not stored
in the ROM's encounter records, which only hold each slot's species and
level(s)); slots for the same species and level(s) are combined into one row
with their chances summed rather than shown as repeated rows.

Special-encounter categories are also extracted: swarms, time-of-day
replacements, and dual-slot substitutions (from connecting a Game Boy Advance
game via dual-slot mode) each replace a specific walking-slot species only, so
the level and chance shown for them are that slot's own values, not separate
ROM data. Poké Radar encounters are shown with species and type but no fixed
level or chance, since the ROM only populates that table for one specific
shake outcome and most radar encounters instead continue the current chain's
species. Unown's per-area letter set is resolved from the ROM's own table
index. The Great Marsh and Trophy Garden daily rotations, which reuse two of
the same slot positions, are not yet extracted — see "Current status" below.

Extract and render trainer parties:

```console
romwiki extract-trainers ".local/roms/Pokemon - Platinum Version (USA).nds"
romwiki build-trainers ".local/roms/Pokemon - Platinum Version (USA).nds"
```

Trainer pages include battle type, levels, held items, custom moves, the
trainer's own AI battle items (consumables and stat boosters its AI may use on
its own party mid-battle — never given to the player), and exact map locations
resolved from standard trainer objects and literal scripted battle commands.
Archive member IDs provide stable page names even when several trainers share
a name; the catalog's static fallback list also appends each trainer's level
range and party preview so genuinely identical-looking entries (e.g. many
unrelated grunts of the same class) stay distinguishable without opening a
page. Dynamically selected facility and rematch trainers, along with unused
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
encounters; roaming Pokémon activations; honey tree and Great Marsh/Trophy
Garden daily encounter pools; Game Corner prize exchanges; and trainer
references. Each map header keeps a stable page even when several interiors
share the same displayed location name.

Extract and render move mechanics:

```console
romwiki extract-moves ".local/roms/Pokemon - Platinum Version (USA).nds"
romwiki build-moves ".local/roms/Pokemon - Platinum Version (USA).nds"
```

Move pages report the exact type, damage class, power, accuracy, PP, priority,
effect ID, targeting, flag, and contest fields stored in the hack's active move
archive. Move and type names come from configured ROM message tables. The move
records themselves carry only an opaque effect ID — the in-game description
text lives in separate message banks that ROM Wiki does not yet extract — so
PokéDB supplies the effect text and flavor-text quote, alongside canonical
comparison names and fallback metadata; ROM-derived values remain
authoritative for every field the move records store.

Extract and render the item catalog:

```console
romwiki extract-items ".local/roms/Pokemon - Platinum Version (USA).nds"
romwiki build-items ".local/roms/Pokemon - Platinum Version (USA).nds"
```

Item pages combine the ROM item-name table, the 34-byte item mechanics records,
and the ARM9 item-to-archive-member map. The enriched build links overworld and
hidden pickups, shops, wild and trainer held items, trainers' own AI battle
items, gifts, trades, and item-based evolutions. As with abilities and moves,
PokéDB supplies the item's effect description, flavor-text quote, and icon:
the ROM's item records store mechanics, while the in-game description text
lives in message banks that ROM Wiki does not yet extract.

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

Audit a built artifact for oversized pages and broken links before publishing:

```console
romwiki site audit dist
romwiki site audit dist --max-page-kb 512 --max-images 100
```

`--max-page-kb` (default 512) and `--max-images` (default 100) flag pages that
exceed the configured rendered-HTML size or image count. The command exits
with an error if any issues are found; this is the same check the GitHub Pages
workflow runs against the built artifact before deploying.

Preview an individual site with live reload:

```console
python -m mkdocs serve --config-file sites/games/renegade-platinum/mkdocs.yml
```

For a faster frontend development loop, use the lightweight game configuration:

```console
python -m mkdocs serve --dirty --config-file sites/games/renegade-platinum/mkdocs.dev.yml
```

The development configuration keeps every catalog index and its JSON data but
builds only the representative detail pages listed in the game's
`dev-pages.toml`. Each game owns its fixture list, so games from different
generations can select different sections and pages. Use the normal configuration
for final link, navigation, search, and production-build review.

Add `--dev` to any `build-*` command (including `build-game`) to match this at
generation time: only the representative detail pages are rendered, while the
complete datasets, `catalog.json`, and each section's index page are still built.
Raw extraction is reused from the ROM cache when valid. This speeds up local
iteration on renderer changes, since a full `build-game` re-renders every
dataset's complete page set on every run.

```console
romwiki build-game --game renegade-platinum --dev
romwiki build-pokemon --game renegade-platinum --dev
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

PokéDB is consumed as an external reference dataset rather than imported through
its internal implementation. The default local path is `../pokedb/.output/gen4`,
with a configurable remote data-branch fallback for CI.

Beyond canonical names and links, PokéDB supplies the descriptive text the
structured ROM records do not carry: Pokémon genus/height/weight/flavor text,
and — for abilities, moves, and items — the human-readable effect description
and Pokédex-style flavor-text quote, version-matched to the profile's
`base_game` where PokéDB has per-version text. Gen IV ROMs do store their own
Pokédex and description text in separate message banks; ROM Wiki does not yet
extract those banks, so this display text describes the base game and a hack
that edits it is not yet reflected (extracting the ROM's own text banks is a
planned follow-up). ROM-derived values remain authoritative for every
structured field the extraction reads; PokéDB never overrides one and is never
the mechanic baseline for hack-changes comparisons.

Pokémon pages, trainer party members, and items may also reference a sprite or
icon URL selected from PokéDB. Sprites and icons are loaded lazily from the
upstream PokéAPI sprites repository; ROM Wiki does not download, cache, or
publish copies of those image files. Missing or unreachable images degrade to a
text placeholder.

## Legal notice

This repository does not include game images, patches, keys, or extracted
copyrighted assets. Users must supply legally obtained inputs locally. Common game
image and save-file extensions are ignored by Git.

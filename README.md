# ROM Wiki

ROM Wiki extracts structured Pokémon game data from locally supplied ROM images
and publishes normalized datasets and static MkDocs wikis.

The project keeps four concerns separate:

1. platform readers open game containers;
2. engine adapters decode generation-specific records;
3. pipelines normalize, enrich, and compare game data;
4. renderers and site tooling publish human- and machine-readable references.

ROM images, patches, keys, saves, and copyrighted extracted assets are never
committed.

## Supported sites

| Site | Publication model |
| --- | --- |
| Pokémon Platinum | Data-driven Generation IV baseline |
| Pokémon Renegade Platinum | Data-driven comparison against Platinum |
| Pokémon Black & White | Data-driven sibling-version family |
| Pokémon Black 2 & White 2 | Data-driven sibling-version family |
| Pokémon Blaze Black & Volt White | Data-driven paired-hack comparison |
| Pokémon Blaze Black 2 & Volt White 2 | Data-driven paired-hack comparison |
| Pokémon Blaze Black 2 Redux & Volt White 2 Redux | Data-driven paired-hack comparison |
| Pokémon HeartGold & SoulSilver | Unpublished data-driven Generation IV family |
| Pokémon Sacred Gold & Storm Silver | Unpublished paired-hack comparison scaffold |

The mature Generation IV and V engines cover Pokémon, abilities, moves, items,
learnsets, evolutions, machines, encounters, trainers, locations, shops, gifts,
trades, static encounters, and other engine-specific mechanics where exact
extraction is supported. The HGSS engine covers Pokémon, abilities, moves,
items, encounters, trainers, and map-header locations, with explicitly recorded
gaps for trainer payouts and map associations. Each site's data-sources page
records its exact input versions, provenance, and known limitations.

“Data-driven” means a site is generated from normalized ROM datasets; it does
not imply exhaustive extraction of every mechanic. Exact coverage belongs in
the site's data-sources page rather than a broad completion label.

## Setup

ROM Wiki requires Python 3.12 or newer.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev,docs]"
```

Create the ignored local game registry:

```powershell
New-Item -ItemType Directory -Force .local | Out-Null
Copy-Item config/games.example.toml .local/games.toml
```

Paths in `.local/games.toml` are relative to that file:

```toml
version = 1

[games.renegade-platinum]
patched_rom = "roms/Pokemon - Renegade Platinum.nds"
base_rom = "roms/Pokemon - Platinum Version (USA).nds"
```

Committed profiles identify and decode supported ROM revisions; the local
registry only supplies machine-specific paths.

## Common workflows

Identify a configured ROM or its clean comparison base:

```console
romwiki inspect --game renegade-platinum
romwiki inspect --game renegade-platinum --base --json
```

Build every dataset and wiki section for one game:

```console
romwiki build game --game renegade-platinum
```

When a clean base is configured, the build extracts and caches it before
current-game data. It then enriches normalized datasets, writes semantic
comparisons, renders the configured site, and publishes deterministic compressed
data downloads. The owning site is resolved from the profile, so profile and site
IDs do not need to be identical.

Regenerate selected sites, or every published site:

```console
romwiki regenerate platinum renegade-platinum
romwiki regenerate --all
```

`regenerate` preflights every required ROM and PokéDB generation before writing,
then builds and audits the combined artifact. Add `--refresh` to replace current
and baseline extraction caches. After reviewing a complete build, add
`--snapshot` to update the tracked ROM-free publication snapshot:

```console
romwiki regenerate --all --refresh --snapshot
```

For normal development, select one site and optionally reuse unchanged rendered
pages; valid raw caches are reused per dataset and engine:

```console
romwiki regenerate renegade-platinum --incremental
```

Adding another engine does not invalidate existing engines' extraction caches.
Use the complete `--all` workflow only for integrated release validation.
Verified unchanged generation, site builds, audit parsing, and per-site snapshots
are reused automatically. The audit still hashes every HTML file and validates
the complete link graph. Use `--clean` to rebuild publication output, and combine
`--clean --refresh` for an occasional from-scratch release check.

Global diagnostic options precede the command:

```console
romwiki --verbose regenerate --all
```

## Focused development

Single-ROM audit extraction and focused rendered builds are grouped by dataset:

```console
romwiki extract personal --game platinum-us
romwiki extract encounters --game platinum-us
romwiki build pokemon --game renegade-platinum
romwiki build moves --game renegade-platinum --dev
```

Build a sibling-version family into one configured site:

```console
romwiki build family --games black-us white-us --versions black white --site-id black-white
```

Manage baseline caches explicitly when needed:

```console
romwiki baseline build --game renegade-platinum
romwiki baseline build --game renegade-platinum --scope pokemon moves
```

See [CLI reference](docs/cli-reference.md) for every command, input-selection
rule, output option, and compatibility alias.

## Site development

List, build, preview, and audit the site catalog:

```console
romwiki site list
romwiki site serve --all --dev
romwiki site build --all --output dist
romwiki site audit dist
```

Generated game pages are archived per site under `sites/generated-wiki/` rather than
tracked individually. A clean checkout restores them with:

```console
romwiki site restore-snapshot
```

See [Frontend](docs/development/frontend.md) for the shared design system and
development-preview contract.

## Project documentation

- [CLI reference](docs/cli-reference.md): commands, inputs, outputs, and workflows.
- [Architecture](docs/development/architecture.md): extraction and publication
  boundaries.
- [Adding a game](docs/development/adding-a-game.md): implementation checklist.
- [Data contracts](docs/development/data-contracts.md): normalized and published
  JSON guarantees.
- [Frontend](docs/development/frontend.md): templates, catalogs, components, and
  review requirements.

## PokéDB

PokéDB is a local external reference dataset for canonical names, links,
descriptive text, and optional media URLs. Exact mechanics and comparisons remain
ROM-derived.

Build commands derive `../pokedb/.output/gen<N>` from the matched engine by
default. Use `--pokedb` or `--pokedb-root` to select another local output.

## Legal notice

This repository does not include game images, patches, keys, saves, or extracted
copyrighted assets. Users must supply legally obtained inputs locally.

# Operations

See the [README](../README.md) for quick start and the [organization contribution guide](https://github.com/pokelitee/.github/blob/main/CONTRIBUTING.md) for shared PR policies. Run commands from the repository root.

## Local inputs

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
registry only supplies machine-specific paths. It may also set `pokedb_root`, the
directory holding PokéDB's `gen<N>` outputs (see [PokéDB reference
data](#pokédb-reference-data)).

## Generation workflows


Identify a configured ROM or its clean comparison base:

```console
romwiki inspect --game renegade-platinum
romwiki inspect --game renegade-platinum --base --json
```

Build every dataset and public data download for one game:

```console
romwiki build game --game renegade-platinum
```

When a clean base is configured, the build extracts and caches it before
current-game data. It then enriches normalized datasets, writes semantic
comparisons, and publishes deterministic compressed data downloads under the
configured site's `wiki/data/`. The owning site is resolved from the profile, so
profile and site IDs do not need to be identical.

Generate selected sites, or every published site, from the site catalog without
repeating their profiles and version labels (`regenerate` is an alias):

```console
romwiki generate platinum renegade-platinum
romwiki generate --all
```

`generate` preflights every required ROM and PokéDB generation before writing,
then generates the selected sites. Add `--refresh` to replace current and
baseline extraction caches. After reviewing a complete generation, update the
frontend snapshot (see [Publication snapshots](#publication-snapshots)).

For normal development, select one site; valid raw caches are reused per dataset
and engine. Adding another engine does not invalidate existing engines'
extraction caches. Use the complete `--all` workflow only for integrated release
validation. Verified unchanged generation and per-site snapshots are reused
automatically. Use `--clean` to regenerate unchanged sites, and combine
`--clean --refresh` for an occasional from-scratch release check.

Global diagnostic options precede the command:

```console
romwiki --verbose generate --all
```

## Focused development

Single-ROM audit extraction and focused section builds are grouped by dataset:

```console
romwiki extract personal --game platinum-us
romwiki extract encounters --game platinum-us
romwiki build pokemon --game renegade-platinum
romwiki build moves --game renegade-platinum
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

See [CLI reference](cli-reference.md) for every command, input-selection
rule, and output option.

## Site catalog

List the site catalog:

```console
romwiki site list
```

## Publication snapshots

The only publication snapshot is the complete frontend snapshot pinned by
`sites/frontend-snapshot/manifest.json`. It includes every published game's
sections, guides, downloads, and comparisons, so a clean checkout can restore the
site without ROMs or PokéDB. See the [frontend guide](development/frontend.md)
for restoring and updating it.

## PokéDB reference data


PokéDB is a local external reference dataset for canonical names, links,
descriptive text, and optional media URLs. Exact mechanics and comparisons remain
ROM-derived.

Commands pick the `gen<N>` output matching the ROM's engine from the PokéDB
root. The root is `--pokedb-root` (or a full `--pokedb` path) when given, else
`pokedb_root` in `.local/games.toml`, else `../pokedb/.output` beside the
repository.

Use the current [PokéDB data contract](https://github.com/pokelitee/pokedb/blob/main/docs/data-contract.md) when updating this integration. PokéDB supplies reference names and descriptive data; it must not replace exact ROM mechanics. Record the inputs and limitations in each site's data-sources page.

## Published site coverage


| Site | Publication model |
| --- | --- |
| Pokémon FireRed & LeafGreen | Data-driven Generation III sibling-version family |
| Pokémon FireRed Omega | Data-driven comparison against FireRed |
| Pokémon Emerald | Data-driven Generation III retail reference |
| Pokémon Platinum | Data-driven Generation IV baseline |
| Pokémon Renegade Platinum | Data-driven comparison against Platinum |
| Pokémon HeartGold & SoulSilver | Data-driven sibling-version family |
| Pokémon Sacred Gold & Storm Silver | Data-driven paired-hack comparison |
| Pokémon Black & White | Data-driven sibling-version family |
| Pokémon Blaze Black & Volt White | Data-driven paired-hack comparison |
| Pokémon Black 2 & White 2 | Data-driven sibling-version family |
| Pokémon Blaze Black 2 & Volt White 2 | Data-driven paired-hack comparison |
| Pokémon Blaze Black 2 Redux & Volt White 2 Redux | Data-driven paired-hack comparison |

The mature Generation IV and V engines cover Pokémon, abilities, moves, items,
learnsets, evolutions, machines, encounters, trainers, locations, shops, gifts,
trades, static encounters, and other engine-specific mechanics where exact
extraction is supported. The HGSS engine covers Pokémon, abilities, moves,
items, encounters, trainers, and map-header locations, with explicitly recorded
gaps for trainer payouts and map associations. The Generation III engines
cover Pokémon, abilities, moves, items, learnsets, machines, move tutors,
encounters, trainers, and locations. Each site's data-sources page
records its exact input versions, provenance, and known limitations.

“Data-driven” means a site is generated from normalized ROM datasets; it does
not imply exhaustive extraction of every mechanic. Exact coverage belongs in
the site's data-sources page rather than a broad completion label.

## CI and GitHub Pages

The React site is live on GitHub Pages. Every PR and main-branch CI run restores the checksum-pinned complete frontend snapshot, checks coverage, builds React, runs desktop/mobile browser tests across every game, and uploads a Pages artifact. PR runs stop there.

CI retains the Python matrix and stable `CI gate`, and adds frontend lint, typing, unit tests, build, and synthetic browser regression tests. Current-site CI uses the complete React snapshot.

Complete React publication data is prepared with `romwiki site export-web --data-root build/data`, then packaged with `romwiki site snapshot-web`, which writes `sites/frontend-snapshot/manifest.json` to pin the archive and every resource checksum, uploads the archive to the existing `snapshots` release under its content-addressed name, and deletes superseded archives other than the one `main` pins. No new release or archive tag is needed. See the [frontend guide](development/frontend.md) for restoration from a clean checkout.

The browser generator's PokéDB packs are published the same way: after PokéDB changes, `romwiki site pack-pokedb` writes `sites/generator-runtime/manifest.json` and uploads the `pokedb-*.tar` archive to the same release, pruning superseded `pokedb-*` archives other than the one `main` pins. The Pages build restores it and bundles the generator; see the [frontend guide](development/frontend.md#browser-generator-runtime).

For review, download the `github-pages` artifact from a successful CI run and extract its `artifact.tar` into a temporary directory. Serve it below `/rom-wiki/` using `python scripts/serve_frontend.py --directory PATH_TO_EXTRACTED_ARTIFACT`, then open `http://127.0.0.1:4173/rom-wiki/`.

A push to `main` deploys automatically: once the `CI gate` passes, CI's `Deploy Pages` job publishes the artifact that run already built and tested to the `github-pages` environment. That environment accepts deployments only from `main`. Superseded PR runs are cancelled, but `main` runs always finish, and deployments are serialized, so a newer merge never interrupts one in progress. If a deployment fails or Pages needs republishing, run the `Deploy Pages` workflow manually from `main`; it repeats the checks and publication build before deploying.

Superseded snapshot archives are deleted, so data cannot be rolled back by reverting the manifest; to restore earlier data, regenerate it and publish a new snapshot. Frontend source changes can still be reverted through a PR.

## Troubleshooting and recovery

- **`romwiki` is not found:** activate the virtual environment used during installation, or invoke `python -m romwiki` with that environment's Python.
- **Missing or unmatched ROM:** check the ignored local registry, relative paths, and the exact profile revision. Registration supplies a path; it does not prove that the image matches the profile. Never commit an image to resolve CI failures.
- **Missing PokéDB generation:** generate the required generation, then point `pokedb_root` in `.local/games.toml` at its output root or pass the CLI's `--pokedb` / `--pokedb-root` options. Consult the CLI reference for command-specific inputs.
- **Unexpected cached output:** use the focused workflow first. `--refresh` replaces extraction caches; `--clean` regenerates sites whose inputs are unchanged. These flags address different layers.
- **Missing generated data in a clean checkout:** restore the publication snapshot. Do not substitute incomplete local outputs for a reviewed snapshot.
- **Snapshot asset is not published:** the manifest references an archive that was never uploaded or has since been superseded. Rerun `romwiki site snapshot-web` from a checkout with the matching exported data. A checksum mismatch means the downloaded asset is not the archive the manifest describes; publish a new snapshot rather than replacing the asset.

Do not force-push source history or rewrite archive tags. Build caches can be discarded and regenerated; local user-supplied inputs cannot be recreated from the repository.

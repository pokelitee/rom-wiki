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
registry only supplies machine-specific paths.

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

Regenerate selected sites, or every published site:

```console
romwiki regenerate platinum renegade-platinum
romwiki regenerate --all
```

`regenerate` preflights every required ROM and PokéDB generation before writing,
then generates the selected sites. Add `--refresh` to replace current and
baseline extraction caches. After reviewing a complete generation, add
`--snapshot` to update the ROM-free publication snapshot, then publish its
archives and commit the manifest (see [Publication snapshots](#publication-snapshots)):

```console
romwiki regenerate --all --refresh --snapshot
romwiki site publish-snapshot
```

For normal development, select one site; valid raw caches are reused per dataset
and engine. Adding another engine does not invalidate existing engines'
extraction caches. Use the complete `--all` workflow only for integrated release
validation. Verified unchanged generation and per-site snapshots are reused
automatically. Use `--clean` to regenerate unchanged sites, and combine
`--clean --refresh` for an occasional from-scratch release check.

Global diagnostic options precede the command:

```console
romwiki --verbose regenerate --all
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

For normal catalog-driven work, generate one or every configured game site without
manually repeating its profiles and version labels:

```console
romwiki generate renegade-platinum
romwiki generate --all
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

Generated data downloads are archived per site rather than tracked individually.
A clean checkout restores them with:

```console
romwiki site restore-snapshot
```

## Publication snapshots

Each per-site snapshot archive contains that site's generated public data: the
`wiki/data/manifest.json` download manifest and every archive it lists. Only
`sites/generated-wiki/manifest.json` is tracked. The per-site archives it
references are ignored locally and published as immutable assets of the
`snapshots` GitHub release. Asset names are content-addressed
(`<site>-<first 16 hex digits of the archive SHA-256>.tar.gz`), so an older
manifest remains restorable after newer snapshots are published.

`restore-snapshot` uses a local archive when its SHA-256 matches the manifest.
Otherwise it downloads the asset into `.romwiki/snapshot-cache/` and verifies the
checksum before extracting anything. Set `ROMWIKI_SNAPSHOT_URL` or pass
`--snapshot-url` to restore from a fork or mirror. Restores never need PokéDB;
the manifest records a PokéDB fingerprint only as provenance when one was
available while snapshotting.

To update the publication snapshot:

1. Regenerate with `romwiki regenerate --all --refresh --snapshot`, or run
   `romwiki site snapshot --pokedb-root ../pokedb/.output` after a verified
   generation.
2. Upload the new archives with `romwiki site publish-snapshot`. It requires an
   authenticated `gh` CLI with write access, verifies every local archive against
   the manifest, creates the release if needed, and uploads only missing assets.
   It never replaces or deletes existing assets.
3. Commit the updated manifest with the source and profile changes that produced
   it, and open a PR.

Publish the assets before pushing the manifest so a clean checkout can restore
it. CI does not restore snapshots. Do not delete release assets that any
reachable manifest still references.

## PokéDB reference data


PokéDB is a local external reference dataset for canonical names, links,
descriptive text, and optional media URLs. Exact mechanics and comparisons remain
ROM-derived.

Build commands derive `../pokedb/.output/gen<N>` from the matched engine by
default. Use `--pokedb` or `--pokedb-root` to select another local output.


Use the current [PokéDB data contract](https://github.com/pokelitee/pokedb/blob/main/docs/data-contract.md) when updating this integration. PokéDB supplies reference names and descriptive data; it must not replace exact ROM mechanics. Record the inputs and limitations in each site's data-sources page.

## Published site coverage


| Site | Publication model |
| --- | --- |
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
gaps for trainer payouts and map associations. Each site's data-sources page
records its exact input versions, provenance, and known limitations.

“Data-driven” means a site is generated from normalized ROM datasets; it does
not imply exhaustive extraction of every mechanic. Exact coverage belongs in
the site's data-sources page rather than a broad completion label.

## CI and GitHub Pages

The React site is live on GitHub Pages; publishing remains manual. Every PR and main-branch CI run restores the checksum-pinned complete frontend snapshot, checks coverage, builds React, runs desktop/mobile browser tests across every game, and uploads a Pages artifact. These CI runs do not deploy.

CI retains the Python matrix and stable `CI gate`, and adds frontend lint, typing, unit tests, build, and synthetic browser regression tests. Current-site CI uses the complete React snapshot rather than restoring retired wiki archives. `romwiki site restore-data` remains available for historical recovery of normalized downloads; those archives are historical publications, not evidence that current extractor code produced them.

Complete React publication data is prepared with `romwiki site export-web --data-root build/data`, then packaged locally with `romwiki site snapshot-web`. The reviewed archive is uploaded under its unique content-addressed name to the existing `snapshots` release; `sites/frontend-snapshot/manifest.json` pins the archive and every resource checksum. No new release or archive tag is needed. See the [frontend guide](development/frontend.md) for restoration from a clean checkout.

For review, download the `github-pages` artifact from a successful CI run and extract its `artifact.tar` into a temporary directory. Serve it below `/rom-wiki/` using `python scripts/serve_frontend.py --directory PATH_TO_EXTRACTED_ARTIFACT`, then open `http://127.0.0.1:4173/rom-wiki/`.

After cutover authorization and a successful PR merge, manually run `Deploy Pages` from `main` with `publish=true`. The workflow repeats both the checks and the complete publication build before deployment to the existing `github-pages` environment. `publish=false` is the default and builds without deploying; other branches cannot deploy. There is no automatic deployment on push or CI completion.

For rollback, revert the frontend source and/or snapshot manifest through a PR and repeat the reviewed manual deployment. The pre-migration MkDocs implementation is preserved at `04b72f2`; restoring that stack requires a separate change, not merely a React snapshot rollback.

## Troubleshooting and recovery

- **`romwiki` is not found:** activate the virtual environment used during installation, or invoke `python -m romwiki` with that environment's Python.
- **Missing or unmatched ROM:** check the ignored local registry, relative paths, and the exact profile revision. Registration supplies a path; it does not prove that the image matches the profile. Never commit an image to resolve CI failures.
- **Missing PokéDB generation:** generate the required generation in the sibling checkout or select another output using the CLI's `--pokedb` / `--pokedb-root` options. Consult the CLI reference for command-specific inputs.
- **Unexpected cached output:** use the focused workflow first. `--refresh` replaces extraction caches; `--clean` regenerates sites whose inputs are unchanged. These flags address different layers.
- **Missing generated data in a clean checkout:** restore the publication snapshot. Do not substitute incomplete local outputs for a reviewed snapshot.
- **Snapshot asset is not published:** the manifest references archives that were never uploaded. Run `romwiki site publish-snapshot` from the checkout that created them. A checksum mismatch means the downloaded asset is not the archive the manifest describes; never replace release assets to fix it.

To restore a previous snapshot, revert the relevant source and manifest changes through a PR. Do not force-push source history or rewrite archive tags. Build caches can be discarded and regenerated; local user-supplied inputs cannot be recreated from the repository.

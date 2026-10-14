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

## Generation and publication workflows


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
`--snapshot` to update the ROM-free publication snapshot, then publish its
archives and commit the manifest (see [Publication snapshots](#publication-snapshots)):

```console
romwiki regenerate --all --refresh --snapshot
romwiki site publish-snapshot
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

For normal catalog-driven work, generate one or every configured game site without
manually repeating its profiles and version labels:

```console
romwiki generate renegade-platinum --dev
romwiki generate --all --dev
```

Manage baseline caches explicitly when needed:

```console
romwiki baseline build --game renegade-platinum
romwiki baseline build --game renegade-platinum --scope pokemon moves
```

See [CLI reference](cli-reference.md) for every command, input-selection
rule, and output option.

## Site development

List, build, preview, and audit the site catalog:

```console
romwiki site list
romwiki site build --all --dev
romwiki site serve --all --dev
romwiki site build --all --output dist
romwiki site audit dist
```

Generated game pages are archived per site rather than tracked individually. A
clean checkout restores them with:

```console
romwiki site restore-snapshot
```

## Publication snapshots

Only `sites/generated-wiki/manifest.json` is tracked. The per-site archives it
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

PR CI downloads and validates the snapshot, so publish the assets before pushing
the manifest. Do not delete release assets that any reachable manifest still
references.

See [Frontend](development/frontend.md) for the shared design system and
development-preview contract.

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

Rendered encounter tables aggregate exact slots by species and form without
changing the downloads. Generation V seasons share canonical `map-NNN` pages.
Trainer relationships are resolved by the owning engine and shown as complete
party tabs, while typed routes such as `trainer-0782` and `header-191` remain
separate from native ROM identifiers.

“Data-driven” means a site is generated from normalized ROM datasets; it does
not imply exhaustive extraction of every mechanic. Exact coverage belongs in
the site's data-sources page rather than a broad completion label.

## CI and GitHub Pages

`.github/workflows/ci.yml` runs the reusable `checks.yml` matrix for PRs and pushes to `main`. `.github/workflows/deploy-pages.yml` runs after a successful CI run for a push to `main` and deploys exactly the commit CI validated. Rulesets block direct pushes, so each `main` commit is one PR merge; deployment compares it with its first parent and skips the build unless `src/`, `sites/`, `profiles/`, `requirements/`, `pyproject.toml`, or the deployment workflow changed. Contributor-documentation-only changes therefore do not trigger a wiki build. Manual dispatch from `main` always deploys. All jobs have explicit timeouts; Actions are pinned to commit SHAs and dependencies to the requirement files.

Deployment does not rerun the test suite that CI already passed. It resolves the published site catalog, downloads and restores each data-driven site's published snapshot, builds sites in parallel, assembles their artifacts, and audits the complete rendered link graph before publishing. Site build caches are keyed by `romwiki site fingerprint`, which hashes source contents so checkout and restore timestamps do not defeat reuse. Site, snapshot-download, and audit caches accelerate builds but do not replace validation. The Pages source is GitHub Actions; the `github-pages` environment permits only `main`.

ROM extraction is never performed in GitHub Actions. The tracked manifest and its published release assets form a deliberate reviewed snapshot model, not an automated `data` branch. Commit manifest changes through PRs with the relevant source/profile/provenance changes. Keep ROM images, patches, saves, keys, and extracted copyrighted assets local and ignored.

```sh
gh workflow run deploy-pages.yml --repo pokelitee/rom-wiki --ref main
gh run list --repo pokelitee/rom-wiki --workflow deploy-pages.yml
```

Read-only default Actions permissions apply. The prepare job has Pages configuration access, and only the final deployment job receives the OIDC token and Pages publishing permissions. Test and build jobs do not retain checkout credentials.

## Troubleshooting and recovery

- **`romwiki` is not found:** activate the virtual environment used during installation, or invoke `python -m romwiki` with that environment's Python.
- **Missing or unmatched ROM:** check the ignored local registry, relative paths, and the exact profile revision. Registration supplies a path; it does not prove that the image matches the profile. Never commit an image to resolve CI failures.
- **Missing PokéDB generation:** generate the required generation in the sibling checkout or select another output using the CLI's `--pokedb` / `--pokedb-root` options. Consult the CLI reference for command-specific inputs.
- **Unexpected cached output:** use the focused workflow first. `--refresh` replaces extraction caches; `--clean` rebuilds publication output. These flags address different layers.
- **Missing generated pages in a clean checkout:** restore the publication snapshot before building. Do not substitute incomplete local outputs for a reviewed snapshot.
- **Snapshot asset is not published:** the manifest references archives that were never uploaded. Run `romwiki site publish-snapshot` from the checkout that created them. A checksum mismatch means the downloaded asset is not the archive the manifest describes; never replace release assets to fix it.
- **Audit or deployment failure:** inspect the failed site, missing links, or snapshot mismatch; repair and rerun rather than skipping the audit. Failed builds do not deploy an incomplete combined artifact.

To restore a previous publication, revert the relevant source and snapshot changes through a PR, pass CI, and let the normal main deployment rebuild it. Do not force-push source history or rewrite archive tags. Build caches can be discarded and regenerated; local user-supplied inputs cannot be recreated from the repository.

# CLI reference

ROM Wiki exposes six top-level command groups:

```text
inspect     identify one ROM and optionally write an input manifest
extract     write one normalized single-ROM audit dataset
build       extract, enrich, compare, and render game data
regenerate  regenerate sites from the site catalog
baseline    manage clean-ROM extraction caches
site        list, build, serve, audit, snapshot, and restore sites
```

Use `romwiki <command> --help` and nested help such as
`romwiki build game --help` for the authoritative option list.

Global `--verbose` and `--quiet` options must precede the command:

```console
romwiki --verbose regenerate --all
```

Default informational logs report command lifecycles and bounded progress for
long-running work at the ROM, dataset, site, page, link, and snapshot levels.
Individual records and files are not logged. `--verbose` adds diagnostic detail;
`--quiet` retains warnings and errors while suppressing routine progress. Lifecycle
messages consistently use `started`, `completed in`, and `failed after` wording.

## ROM inputs

Commands that operate on one ROM accept a configured game or explicit path:

```console
romwiki inspect --game renegade-platinum
romwiki inspect --rom "D:\Games\patched.nds"
```

`--game` resolves a path from `.local/games.toml`. `--rom` is an explicit
one-command override.

Use `--base` with `--game` to select that registration's clean base image:

```console
romwiki inspect --game renegade-platinum --base
```

Use `--games-config` or `--profiles-dir` to replace their repository defaults.
Path registration does not make an unsupported ROM extractable; the selected
image must still match a committed profile.

## Inspect

Identify a ROM:

```console
romwiki inspect --game platinum-us
romwiki inspect --game platinum-us --json
```

Write a versioned provenance manifest:

```console
romwiki inspect --game platinum-us --manifest-output build/data/manifest.json
```

The manifest is a standalone audit record. Extraction caches and later build
stages maintain their own manifests and do not consume this file.

## Extract

`extract` writes one normalized single-ROM audit dataset without enrichment,
comparison, or rendering:

```console
romwiki extract personal --game platinum-us
romwiki extract encounters --game platinum-us
romwiki extract trainers --game platinum-us
```

Available kinds are:

| Kind | Default output below `build/data/<profile>/` |
| --- | --- |
| `personal` | `pokemon/personal.json` |
| `learnsets` | `pokemon/learnsets.json` |
| `egg-moves` | `pokemon/egg-moves.json` |
| `evolutions` | `pokemon/evolutions.json` |
| `machines` | `machines/raw.json` |
| `tutors` | `tutors/raw.json` |
| `pickup` | `pickup/raw.json` |
| `moves` | `moves/raw.json` |
| `items` | `items/raw.json` |
| `encounters` | `encounters/raw.json` |
| `trainers` | `trainers/raw.json` |
| `locations` | `locations/raw.json` |

Every kind accepts `--output` to replace its default file.

## Build

Build commands load the generation-appropriate PokéDB directory automatically.
Use `--pokedb` to override it.

### One game

The normal per-game workflow is:

```console
romwiki build game --game renegade-platinum
```

It builds all normalized datasets, comparisons, public downloads, and rendered
sections. When the profile belongs to one catalog site, that site's wiki root is
selected automatically. Use `--wiki-root` only for an intentional alternative
destination.

Configured builds use `base_rom` when the registration defines one. Registrations
without a base build as standalone games. For explicit paths, supply `--base-rom`;
use `--hack-only` only when intentionally omitting comparisons:

```console
romwiki build game --rom "D:\Games\hack.nds" --base-rom "D:\Games\base.nds"
romwiki build moves --rom "D:\Games\hack.nds" --hack-only
```

Current-ROM extraction is cached below `build/data/cache/<profile>/`; clean
baselines are cached below `build/data/baselines/<base-profile>/`.
`--refresh-cache` and `--refresh-baseline` replace those caches.
Cache validation is dataset- and engine-scoped: changing a pipeline extractor
rebuilds its affected raw dataset, while engine changes leave other engines'
caches intact. A ROM or resolved-profile change invalidates the profile's complete
cache. Cache manifest schema upgrades also cause a one-time complete rebuild.

### One section

Focused section builds remain available for renderer and extraction development:

```console
romwiki build pokemon --game renegade-platinum
romwiki build encounters --game renegade-platinum
romwiki build trainers --game renegade-platinum
romwiki build locations --game renegade-platinum
romwiki build moves --game renegade-platinum
romwiki build items --game renegade-platinum
```

They follow the same baseline policy as a full game build. `--data-output` names
the primary dataset file, while `--wiki-output` names the generated section
directory. `--dev` renders only the representative detail pages declared by the
site's `dev-pages.toml`, while retaining complete catalog data.

The same flag is available for a complete single-game or sibling-family data
build. This regenerates the lightweight Markdown selected by the manifest
without building or serving MkDocs:

```console
romwiki build game --game renegade-platinum --dev
romwiki build family --games black-us white-us --versions black white --site-id black-white --dev
```

### Sibling-version family

Two or more sibling versions can publish into one site:

```console
romwiki build family --games black-us white-us --versions black white --site-id black-white
```

`--site-id` is required. Each version label tags shared and exclusive records.
If any registration defines `base_rom`, every registration in the family must
define one so comparisons can be merged consistently.

## Regenerate

`regenerate` is the complete catalog-driven workflow:

```console
romwiki regenerate platinum renegade-platinum
romwiki regenerate --all
romwiki regenerate heart-gold-soul-silver --incremental
```

It:

1. validates every selected site, local ROM registration, profile match, and
   PokéDB generation;
2. dispatches single-profile and version-family data builds;
3. builds the selected MkDocs sites into one artifact;
4. audits the combined artifact.

Normal runs reuse validated caches. `--refresh` replaces current and baseline
caches. `--snapshot` is restricted to `--all` and archives the successfully
audited generated content:

```console
romwiki regenerate --all --refresh --snapshot
```

Complete regeneration safely reuses metadata-verified generation and build source
state by default. The complete workflow verifies the exact output path set, hashes
every HTML file, and validates the full link graph. `--clean` bypasses publication
reuse and reparses the audit while repopulating its cache; `--refresh` separately
replaces ROM extraction caches. Use `site audit --no-cache` to bypass only the
audit parse cache.

`--incremental` retains the selected site's existing artifact and asks MkDocs to
process only added or changed source files. ROM extraction caches and deterministic
rendering still run normally; unchanged generated files retain their modification
times, so MkDocs can skip them. A metadata inventory under
`.romwiki/build-state/` binds reuse to the output path, production/development
mode, site URL, MkDocs versions, site configuration, shared templates and hooks,
and the complete source-file set. Missing output, changed build inputs, or deleted
or renamed sources automatically select a clean site build.

Use a site ID without `--all` while developing a new game or generation. This
extracts and renders only that selection, reuses valid per-dataset caches, and
leaves unrelated games untouched. Reserve `regenerate --all` for final integrated
validation and snapshot publication.

Snapshot creation rejects `--incremental`. Publication snapshots must always come
from the complete audited `--all` workflow; verified unchanged sites may be reused.

## Baseline caches

Warm every clean-ROM baseline dataset or a selected scope:

```console
romwiki baseline build --game renegade-platinum
romwiki baseline build --game renegade-platinum --scope pokemon moves
```

Use `--refresh` to replace valid baseline cache entries.

## Sites

List all sites or published automation metadata:

```console
romwiki site list
romwiki site list --published --json
```

Build one or every published site:

```console
romwiki site build renegade-platinum --output dist
romwiki site build renegade-platinum --output dist --incremental
romwiki site build renegade-platinum --output dist --reuse-unchanged
romwiki site build --all --output dist
```

Serve a focused selection or every published site with live reload:

```console
romwiki site serve renegade-platinum --dev
romwiki site serve --all --dev
```

Audit a combined artifact:

```console
romwiki site audit dist
romwiki site audit dist --max-page-kb 512 --max-images 150
```

Create or restore the deterministic ROM-free publication snapshot:

```console
romwiki site snapshot
romwiki site restore-snapshot
romwiki site restore-snapshot --site renegade-platinum
```

The tracked snapshot is a manifest plus deterministic per-site archives under
`sites/generated-wiki/`. Metadata inventories avoid rereading unchanged generated
content; content hashes remain the fallback when metadata changes. Unchanged
archives are not rewritten. Snapshot creation and restore report bounded,
site-level progress so long hashing and archive operations remain visible without
logging individual files. Restore continues to accept the former monolithic archive
during migration. For compatibility, an explicit `.tar.gz` output keeps `site
snapshot` in the monolithic format.

Prefer `romwiki regenerate --all --snapshot` when ROM inputs are available,
because it guarantees generation, site building, and auditing succeeded before
the snapshot is replaced.

# CLI reference

ROM Wiki exposes six top-level command groups:

```text
inspect     identify one ROM and optionally write an input manifest
extract     write one normalized single-ROM audit dataset
build       extract, enrich, compare, and export game data
generate    generate site data from the site catalog (alias: regenerate)
baseline    manage clean-ROM extraction caches
site        list sites and snapshot, restore, or publish generated data
```

Use `romwiki <command> --help` and nested help such as
`romwiki build game --help` for the authoritative option list.

Global `--verbose` and `--quiet` options must precede the command:

```console
romwiki --verbose generate --all
```

Default informational logs report command lifecycles and bounded progress for
long-running work at the ROM, dataset, site, and snapshot levels.
Individual records and files are not logged. `--verbose` adds diagnostic detail;
`--quiet` retains warnings and errors while suppressing routine progress. Lifecycle
messages consistently use `started`, `completed in`, and `failed after` wording.

Commands exit with status `0` on success and `1` when a ROM Wiki error, such as a
missing ROM, an unmatched profile, or a stale snapshot, stops the command. Status
`2` is reserved for usage errors reported by argument parsing, such as an unknown
option.

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
comparison, or export:

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

It builds all normalized datasets, comparisons, and public data downloads. When
the profile belongs to one catalog site, that site's wiki root is selected
automatically and the downloads are written to its `wiki/data/`. Use
`--wiki-root` only for an intentional alternative destination.

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

Focused section builds remain available for extraction development:

```console
romwiki build pokemon --game renegade-platinum
romwiki build encounters --game renegade-platinum
romwiki build trainers --game renegade-platinum
romwiki build locations --game renegade-platinum
romwiki build moves --game renegade-platinum
romwiki build items --game renegade-platinum
```

They follow the same baseline policy as a full game build and write the section's
dataset, comparison, and public download. `build pokemon` also writes the
abilities and type-chart datasets. `--data-output` names the primary dataset
file, and `--wiki-root` replaces the wiki root that receives the download.

### Sibling-version family

Two or more sibling versions can publish into one site:

```console
romwiki build family --games black-us white-us --versions black white --site-id black-white
```

`--site-id` is required. Each version label tags shared and exclusive records.
If any registration defines `base_rom`, every registration in the family must
define one so comparisons can be merged consistently.

## Generate

`generate` is the catalog-driven ROM-to-data workflow. It reads each site's
`game.toml` and automatically dispatches a single-profile or version-family
build:

```console
romwiki generate renegade-platinum
romwiki generate black-white
romwiki generate --all
```

Valid extraction caches are reused. Use `--refresh` to replace extraction caches
or `--clean` to bypass unchanged-generation reuse.

Selected sites are generated in parallel worker processes, one per CPU by
default; `--jobs` caps the worker count and `--jobs 1` generates sites one after
another in the current process. Sites that share an extraction cache, such as two
hacks of the same clean base ROM, are generated in sequence by one worker. Each
worker's log lines are prefixed with its site ID. A failing site does not stop the
other workers; the command reports the first failure once every site has settled.
Each worker loads only the PokéDB generations its sites need, so peak memory grows
with the worker count.

`regenerate` is an alias of `generate`; both run the same workflow.

It validates every selected site, local ROM registration, profile match, and
PokéDB generation before writing, and skips sites whose generation inputs and
generated files are unchanged.

Use a site ID without `--all` while developing a new game or generation. This
extracts and writes only that selection, reuses valid per-dataset caches, and
leaves unrelated games untouched. Reserve `generate --all` for final integrated
validation before preparing a frontend snapshot.

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

### React frontend data

```sh
romwiki site export-web --data-root build/data
romwiki site snapshot-web
romwiki site restore-web .romwiki/frontend-snapshot
```

`export-web` requires all comparative games to have complete comparison inputs and writes the React publication contract. `snapshot-web` packages only referenced resources into a deterministic local archive and checksum manifest. `restore-web` accepts that manifest directory and verifies the archive and resources before restoration. These commands do not publish releases or deploy the site.

# Architecture

ROM Wiki turns game-specific binary data into normalized records and then renders
those records as static documentation. The intended flow is:

```text
configured clean ROM                configured patched ROM
        |                                   |
        v                                   v
identify -> decode -> normalized raw cache  identify -> decode -> normalized raw data
        |                                   |
        +----------------+------------------+
                         v
          engine normalization and enrichment
                         |
                         v
              semantic dataset comparison
                         |
                         v
                 renderer -> MkDocs site
```

The key design rule is that renderers consume normalized data. They must not read
ROM offsets, archive members, script opcodes, or other engine-specific structures.
Engine-specific encodings are translated before enrichment; enrichment resolves
cross-dataset identities and optional reference media without interpreting binary
mechanics.

## Local input registry

Committed profiles describe how to identify and decode an image, but never contain
machine-specific ROM paths. The ignored `.local/games.toml` registry associates a
game ID with `patched_rom` and optional `base_rom` paths. Relative paths resolve
from the registry's directory. CLI commands accept `--game` to select the patched
path and `--base` to select the clean baseline; explicit and legacy positional ROM
paths remain supported.

Path registration and format support are separate. The registry validates that the
selected file exists, after which normal profile identification still determines
whether extraction may proceed. Comparison workflows should normalize each input
independently and compare those datasets rather than comparing ROM bytes.

The `platinum-us` profile is the verified clean baseline for Renegade Platinum. It
uses the same `gen4_dppt` engine while retaining retail-specific profile metadata,
including its ROM version, hash, and egg-gift script offsets. Selecting
`renegade-platinum` with `--base` resolves the local base path; profile
identification then assigns extracted datasets to `platinum-us`. Generated baseline
raw data remains under ignored `build/data/baselines/platinum-us/` paths. Cache
manifests bind those files to the base profile, exact ROM SHA-256, schema version,
and an explicit cache revision.

`GameBuildWorkflow` is the dependency-aware orchestration boundary. A complete
build materializes every baseline dataset before any patched dataset, then compares
the normalized outputs. A focused section build still extracts that section's
baseline before its patched equivalent. The escape hatch `--hack-only` is explicit;
configured builds fail clearly when their clean base image is missing.

Comparisons operate on stable normalized keys: Pokémon personal member, numeric
ability/move/item/trainer IDs, encounter area ID, and location header ID. They
classify records as unchanged, changed, added, or removed and retain exact field
deltas. Presentation-only reference objects, sprites, provenance, and engine-only
`source_fields` do not count as game-mechanic changes. Nested relationships compare
stable numeric identities,
so spelling, spacing, or slug changes are reported on the referenced entity rather
than falsely changing every record that links to it. Removed records receive
comparison-only snapshot pages.

## Layers

### Platform readers

`src/romwiki/platforms/` handles game containers without interpreting Pokémon
mechanics. The current NDS implementation validates an image, reads its header and
filesystem, opens NARC archives, and reads overlays.

A future GB/GBC, GBA, or 3DS implementation belongs in its own platform package.
Platform readers should expose bytes and files to an engine decoder while avoiding
game-specific concepts such as encounters or trainer parties.

### Profiles

`profiles/` identifies supported ROM variants by header metadata and cryptographic
hash. A profile records the engine family, internal paths, table offsets, counts,
and narrowly scoped annotations needed for exact extraction.

Profiles describe layout differences; they do not replace parsers. If two hacks
store the same record in the same format at different paths or offsets, they can
normally share an engine decoder and use different profiles. If a hack changes the
record format or script behavior, the engine needs a parser variant or an explicit
capability for that difference.

Platform readers own values encoded by the container itself, and engine decoders
own stable format defaults such as sentinels and standard record counts. A profile
contains only build-specific locators and verified overrides. Relationships that
cannot yet be derived exactly, such as a shared script command's map association,
remain narrow profile annotations rather than hard-coded pipeline branches.

### Engine decoders

`src/romwiki/engines/` groups binary and script parsers first by generation and
then by engine family. The current `gen4/dppt` and `gen5/bw` leaf packages decode
the D/P/Pt and Black/White formats. Their stable profile-facing engine IDs remain
`gen4_dppt` and `gen5_bw`.

A generation package is a namespace, not a selectable engine. When a second
family is implemented, such as `gen5/b2w2` or `gen4/hgss`, begin with a separate
leaf adapter. Promote a parser into the parent generation package only after real
ROM fixtures prove that its format and behavior are shared by at least two
families. Leaf packages may depend on their generation's shared modules, but
must not depend on sibling leaves.

Engine decoders should return typed facts, validate bounds and identifiers, and
avoid page-layout decisions. Exact ROM-derived values take priority over external
documentation.

When an engine stores a semantic value indirectly, its engine package also owns
the translator for that encoding. For example,
`engines/gen4/dppt/trainer_party.py` translates Gen IV trainer-party records into
the shared party contract. `pipeline/trainer_party.py` dispatches by the explicit
`engine` field on the raw dataset; it must not accumulate generation-specific
branches itself.

### Pipelines and normalized schemas

`src/romwiki/pipeline/` joins decoded records into datasets. The dataclasses under
`src/romwiki/schema/` define normalized concepts such as Pokémon personal data,
moves, encounters, trainers, and locations. Datasets carry a `schema_version`, a
game identifier, record counts, source metadata, and record-level provenance where
appropriate.

Enriched datasets also carry a normalized `features` list derived from the engine
adapter and exact profile configuration. Renderers use this contract to distinguish
"this game does not have this mechanic" from "this record has no entries." Version
families may merge only datasets with identical feature contracts; a mismatch fails
at the pipeline boundary instead of producing an internally inconsistent site.

Schema versions for independently emitted contracts are declared centrally in
`schema/versions.py`. Raw and enriched forms have separate constants even when
both are currently version 1. Raw-cache validation selects the expected version
by cache key, so changing one dataset contract does not invalidate unrelated raw
datasets. Independently evolving nested contracts, such as trainer parties, keep
their own schema version alongside the containing dataset's version.

Normalized records use stable semantic fields such as `species_id`, `base_stats`,
or `held_item_id`; they do not expose where a value happened to live in one ROM.
Engine-only details needed for auditing belong in provenance fields.

Trainer party data has its own `party_schema_version` because its optional mechanics
will expand independently of the surrounding trainer dataset. The shared contract
is defined in `schema/trainers.py`. Normalized members state their move source
as `explicit`, `level-up`, or `unavailable` and provide optional ability, nature,
gender, IV, and EV attributes. Present attributes identify their source as
`stored`, `derived`, or `engine-default`; unknown values remain absent rather than
being guessed. The Gen IV adapter derives uniform IVs, the deterministic first
ability slot, zero-EV defaults, nature, and Pokémon gender. Nature and gender use
the engine's deterministic personality algorithm plus the trainer-class gender
table read from ARM9; Pokémon gender also uses the current game's species ratio.
The two-byte Gen IV difficulty value also reproduces the deterministic random-IV
fallback used when its scaled value exceeds 31. The adapter calculates unmodified
summary stats from the current game's base stats, level, IVs, EVs, and nature;
renderers consume those normalized values without implementing a generation's
stat formula.
Raw bytes such as Gen IV `difficulty` remain under `source_fields`; renderers and
semantic comparisons never consume that mapping.

Trainer enrichment resolves Pokémon through the current game's enriched Pokémon
dataset. This is required for hacks that change forms, names, sprites, or ability
slots. PokéDB remains a reference and fallback source, not the authority for a
game's mechanics.

Exact trainer rewards use a shared normalized contract while retaining
generation-specific decoding. Engine parsers expose the stored multiplier and its
provenance; `pipeline/trainer_rewards.py` calculates a payout only when every
required input is exact. AI battle items, post-victory items, and prize money are
separate concepts throughout extraction and rendering. An unsupported or
incomplete payout is omitted rather than estimated.

Derived datasets may invert normalized relationships without parsing the ROM again.
For example, the ability dataset combines the ROM ability-name table with ability
assignments already present in normalized Pokémon records, producing ability pages
and Pokémon backlinks from one authoritative extraction. The item dataset follows
the same pattern, joining normalized mechanics with item references from Pokémon,
trainers, locations, shops, gifts, trades, and evolutions.

Cross-dataset reverse links used only for presentation are built once per full or
version-family build by `pipeline/relationships.py`. Its focused
`RelationshipIndex` covers Pokémon encounters, acquisition sources and trainer
appearances; move learners; and location-to-encounter variants. It preserves stable
IDs, forms, versions, deterministic ordering, and deduplication before a renderer
sees the data. Renderers format those references but do not rescan unrelated
datasets to recreate joins. Focused single-section commands may construct the same
index from companion datasets made available by the build context.

The relationship index is deliberately a presentation artifact, not a normalized
download. Its source facts and forward relationships already exist in the public
datasets; publishing the reverse index would create a second contract that could
drift without adding ROM facts.

Normalized relationships identify entities by stable IDs, not page paths. The
MkDocs reference resolver maps those identities and resolved route keys to Markdown
source links or published directory URLs. This keeps routing out of extraction and
ensures catalog and detail-page links share one implementation.

Type effectiveness follows a separate engine/profile contract. Each data-driven
profile must explicitly select a chart registered by its engine. A hack may declare
additional types and validated sparse matchup overrides; it cannot silently inherit
its parent's chart selection. `pipeline/type_charts.py` validates the complete
effective matrix, represents multipliers exactly, emits the normalized public
`types` dataset, and provides the single defensive calculator reused by Pokémon
pages. Generation-specific registrations point to immutable chart-family data, so
Generations II through V share one authoritative matrix while retaining explicit
`gen2`, `gen3`, `gen4`, or `gen5` profile identity as their engines are added. A
future changed chart receives a new family rather than conditionals in the shared
calculator. This keeps generation mechanics out of renderers while allowing future
ROM-native chart extraction without changing their contract.

`src/romwiki/sources/` enriches normalized ROM facts with external reference data.
ROM message tables supply names when configured; PokéDB supplies canonical names
for comparison and fallback, plus stable links and optional sprite/icon URLs. It
must not override a value extracted from the game. A profile's
`reference.sprite_version` selects matching version sprites; enrichment keeps a
default sprite for compact cards plus every available front/back, normal/shiny,
and gender variant for detail-page galleries. Pokémon records also keep a
deliberately small `reference` object containing descriptive species metadata.

The same `reference` pattern extends to abilities, moves, and items: the ROM
stores their names, ROM-native mechanics, and assignments, but never a
human-readable description of what they do, so `PokeDBGeneration.ability_reference`
/ `move_reference` / `item_reference` (keyed by ROM ID for abilities/moves, by
resolved slug for items, since their ROM item IDs don't align with PokéDB's) are
the sole source for effect text and Pokédex-style flavor-text quotes, matched to
a profile's `base_game` version where PokéDB carries per-version text. Trainer
party members carry a Pokémon sprite and, when applicable, a held-item icon
through the same lookups. PokéDB is never the mechanic baseline: exact change
sections compare the parsed clean ROM with the parsed hack, and ROM-derived
values remain authoritative; the `_clean()` comparison step strips every
`reference`/`sprite`/`sprites` object before diffing so presentation data never
produces a false "changed" result.

### Renderers and sites

`src/romwiki/renderers/` turns normalized datasets into documentation. The MkDocs
renderer has no responsibility for identifying or parsing a ROM.

`sites/games/<slug>/` contains one independently configurable game wiki. The site
catalog builds those wikis and the portal into one GitHub Pages artifact while
preserving stable per-game URLs.

All sites inherit their Material configuration and design system from
`sites/shared/`. A repository-local MkDocs hook loads the site catalog and exposes
the current site plus every published game to the shared templates. The portal and
game selector are therefore generated from site descriptors rather than a second
maintained game list.

Section renderers emit both Markdown and a compact, versioned `catalog.json`.
Shared JavaScript progressively renders searchable and filterable catalog tables;
the Markdown index retains a complete static fallback. Catalog JSON is a
presentation index and does not replace the normalized datasets. Comparative
catalogs share a Change status filter and column. Every current detail page has an
explicit base-game section, including a verified-unchanged state, and the generated
Changes page summarizes all sections.

Full builds also publish each complete normalized dataset as deterministic
`wiki/data/<kind>.json.gz`, plus comparison datasets when present. A
machine-readable manifest records schema versions, record counts, compressed sizes,
and SHA-256 checksums. These archives are the complete data interface; Markdown is
the curated human interface and catalog JSON remains a small presentation index.
Snapshot creation and restoration validate the manifest and every archive.

## Reuse boundaries

There are three common extension cases:

1. **Another hack with the same engine and unchanged formats:** usually a profile,
   site configuration, validation fixtures, and any necessary explicit annotations.
2. **Another game in a partially supported engine family:** reuse the platform and
   common parsers, then add format variants and pipeline capabilities where the base
   game differs.
3. **Another platform or generation:** add a platform reader when necessary, a new
   engine decoder, and a pipeline adapter that emits the existing normalized
   contracts. Existing renderers can then be reused for compatible concepts.

A new engine should not be forced into Generation IV assumptions. If a game has a
real concept that the schemas cannot represent, extend the normalized schema with
an optional or versioned field and update renderers to degrade gracefully for games
that do not provide it.

## Platform and engine registries

`src/romwiki/platforms/registry.py` and `src/romwiki/engines/registry.py` are the
plug-in boundary. Each maps a stable string key (`GameProfile.platform`,
`GameProfile.engine`) to a small adapter exposing that platform's image/filesystem/
archive primitives, or that engine's generation metadata, parsers, and constants.
The CLI uses the engine generation to select the matching local PokéDB output by
default, and the site catalog verifies descriptor generation metadata against it.
Pipeline modules resolve
`get_platform(profile.platform)` and `get_engine(profile.engine)` instead of
importing `platforms.nds` or `engines.gen4.dppt` directly; only the registries
themselves, and each engine/platform's own package, are allowed to name a specific
implementation. `pipeline/trainer_party.py` predates the shared registries and uses
the same dict-dispatch shape locally, scoped to the one contract it translates.

Adding a second platform or engine is additive at the registry boundary: a new
`platforms/<platform>/` or `engines/<generation>/<family>/` package, one new
entry in the relevant registry dict, and a profile that declares the matching
`platform`/`engine` keys. No pipeline module needs to change to *dispatch* to
it. But a pipeline
module that has only ever run against one engine can still carry that engine's
unstated assumptions, invisible until a second real engine exercises the same
code path. Implementing `gen5_bw` (alongside `gen4_dppt`) found two:
`pipeline/locations.py` unconditionally required several Platinum-only Sinnoh
mechanics (honey trees, Trophy Garden, Great Marsh, decorations, seals, Battle
Frontier), and `pipeline/build_context.py` eagerly required several ancillary
Pokémon-enrichment datasets (learnsets, evolutions, machines, tutors, egg
moves, pickup) that don't exist for an engine's first vertical slice. Both were
small, targeted fixes — gate the feature on whether the profile actually
configures it, mirroring the pattern `pipeline/reference_names.py` already used
— not a redesign. Treat this as expected, cheap-to-fix generalization work when
adding a second engine, not evidence the registry boundary is wrong.

`tests/engines/test_contract.py` is the regression guard for this boundary: it
registers a throwaway fake engine at test time and asserts that enrichment and
rendering consume its output correctly, with no gen4-specific branching. Extend
that test file, rather than adding a first real second engine's assumptions to it,
if the contract needs to grow.

## Current limitations

ROM identification already supports blind platform detection: `identify.py`'s
`_inspect_image` tries each platform registered in `platforms/registry.py` in
turn and returns the first one that accepts the image, rather than assuming
Nintendo DS. `tests/platforms/test_contract.py` proves this against a
throwaway fake platform, the same pattern `tests/engines/test_contract.py`
uses for the engine boundary above.

The `gen4_dppt` and `gen5_bw` engines now exercise the same normalized pipeline
and shared renderer system against two real generations, including retail games,
single-version hacks, and sibling-version hack families. Generation-specific
binary decoding stays in each engine package; optional presentation behavior is
advertised through dataset capabilities. This validates the engine boundary
against real data, while a second physical platform remains proven only by
`tests/platforms/test_contract.py`'s fake adapter. A real platform addition should
still add profile-identification, parser, and normalized-output fixtures following
[Adding a game](adding-a-game.md).

Normalized schemas are implemented as Python dataclasses and typed contracts
serialized to JSON.

These are known extension tasks, not reasons to combine extraction and rendering.
The existing boundary remains the intended long-term design.

## Generated publication snapshot

ROM-derived Markdown remains ignored as individual files, but deployment must be
reproducible without distributing ROM inputs. `romwiki site snapshot` packs all
generated game sections and public data archives into the deterministic, tracked
`sites/generated-wiki.tar.gz` archive. The Pages workflow restores that archive
before invoking MkDocs. Its manifest fingerprints the parser, pipeline,
renderer, and profile sources, so a stale snapshot is rejected; publishing-only
build, audit, and MkDocs hook changes do not invalidate generated content.
Required Pokémon, ability, item, move, encounter, trainer, location, type-chart,
and public-data sections are validated before a site build, preventing an absent
publication input from degrading into a successful partial deployment.

`romwiki regenerate` is the catalog-driven owner of complete local regeneration.
It preflights all selected ROM registrations and generation-specific PokéDB
outputs before writing, dispatches single-profile and version-family sites through
their existing build workflows, builds the selected MkDocs sites, and audits the
combined artifact. Snapshot creation is an optional final step restricted to
complete `--all` runs. This orchestration layer does not reimplement extraction,
merging, rendering, site building, auditing, or snapshot behavior.

# Adding a game

The amount of work depends on how closely the new game matches an already supported
platform and engine. Begin by classifying the target before writing parsers.

## Register local inputs

Add development-only paths to `.local/games.toml`, which is ignored by Git:

```toml
[games.example-hack]
patched_rom = "roms/Example Hack.nds"
base_rom = "roms/Example Base Game.nds"
```

Paths are relative to `.local/games.toml`. Use `romwiki inspect --game example-hack`
to verify the patched selection and add `--base` to inspect the clean selection.
Do not put local paths in the committed profile or site descriptor. A registered
base image also needs a matching profile before extraction commands can normalize
it for comparison.

When a hack and its clean base share an engine, keep separate profiles for their
exact releases. Shared parsers do not imply identical metadata: hashes, ROM
versions, script offsets, or repurposed tables may differ. Validate the base profile
through every supported raw extractor and enriched builder before treating it as a
comparison baseline.

Once both images identify correctly, populate and verify the clean cache, then run
the complete comparative workflow:

```console
romwiki baseline build --game example-hack
romwiki build-game --game example-hack
```

Do not build a mechanic baseline from PokéDB. It supplies names, links,
descriptions, and sprites; the separately parsed clean ROM supplies comparison
values. New engines must emit the stable keys needed to align equivalent records.

## 1. Classify the target

- Determine the platform, generation, base game, region, revision, and hack version.
- Record hashes only for the exact legally obtained input variants being supported.
- Compare its container, archives, records, and script commands with an existing
  engine.
- Decide whether the target needs only a profile, an engine variant, or a completely
  new platform and engine adapter.

Examples:

- A Platinum hack that preserves Platinum's layouts can reuse `gen4_dppt` and may
  need mostly profile data and verification.
- A Diamond or Pearl hack can reuse the NDS platform and some Generation IV parsers,
  but Platinum-specific tables and scripts must be audited.
- FireRed Omega needs a GBA platform reader and a Generation III engine decoder.
- A Generation I or II hack needs a GB/GBC platform reader and generation-specific
  decoders.
- Sinking Sapphire needs a Generation VI/3DS input strategy and engine decoder. The
  tool must continue to require user-supplied legal inputs and must not distribute
  keys or copyrighted extracted assets.

## 2. Add identification and layout metadata

Create `profiles/<category>/<game-id>.toml` with:

- a stable profile ID and display name;
- engine and base-game identity (plus platform identity once multi-platform
  dispatch is introduced);
- header identifiers and exact hashes;
- internal paths, offsets, counts, and other layout parameters;
- explicit annotations only when the relationship cannot be derived exactly.

If the new ROM uses an existing profile's complete layout, declare
`extends = "<parent-profile>"` in its `[profile]` table and override only the
fields that differ. Nested TOML tables merge recursively; scalar and array
values in the child replace inherited values. Keep a standalone profile when
the relationship is only approximate or extensive overrides would make
inheritance harder to audit.

Keep format logic out of the profile. A profile should select and configure a
parser, not implement one through a large collection of magic values.

Do not repeat platform or engine invariants in a game profile. Values such as an
ARM executable's load address should come from the container header, while stable
sentinels and table dimensions should be defaults owned by the engine decoder.
Profiles may override an engine default only when a verified ROM variant actually
changes it. Keep exact paths, table offsets, message members, and script anchors in
the profile because those identify where that build stores its data.

When PokéDB contains generation-specific sprites, set the optional reference key:

```toml
[reference]
sprite_version = "platinum"
```

Use the exact key present under PokéDB's `sprites.versions`. If it is absent or its
URL is unavailable, rendered pages use PokéDB's generic sprites and then a
text-only fallback. Sprite availability must never affect extraction success or
comparison status.

The required profile `base_game` should use the corresponding lowercase PokéDB
version key when one exists. Pokémon enrichment uses it to select descriptive
reference text and label comparisons with the unmodified game. Missing reference
fields are optional and must not prevent extraction or page rendering.

Prefer ROM-derived name tables whenever the engine stores them. Profiles identify
the message members, while extraction decodes their contents and records
provenance:

```toml
[parameters]
type_names_member = 624
ability_names_member = 610
item_names_member = 392
move_names_member = 647
```

Enrichment uses those tables consistently in move records, learnsets, trainer
parties, machines, tutors, egg moves, and evolution conditions. Comparing the ROM
move name at an ID with PokéDB also identifies replaced moves without making the
external name authoritative. Semantic overrides remain a fallback for games whose
names cannot be decoded from the image:

```toml
[semantics.types]
9 = "fairy"

[semantics.moves]
66 = "play-rough"
```

Fallback names must be lowercase hyphenated values and must never replace a
successfully decoded ROM name.

Every data-driven profile must explicitly select a type chart registered by its
engine:

```toml
[type_chart]
chart = "gen4"
```

Do not rely on profile inheritance for this declaration: a child hack must make
the choice explicit so altered mechanics cannot silently inherit a base chart.
When a hack adds a type or changes matchups, list the additional types and only
the verified sparse overrides:

```toml
[type_chart]
chart = "gen4"
additional_types = ["fairy"]

[type_chart.overrides]
"fairy>dragon" = "2"
"dragon>fairy" = "0"
```

Override keys are `attacking>defending`; multiplier values use the exact strings
accepted by the type-chart contract. Profile loading and dataset construction
reject unknown types, duplicate or incomplete charts, and invalid multipliers.
When several generations have identical effectiveness rules, register their
generation-specific chart IDs against one immutable family matrix. This preserves
clear profile identity and provenance without duplicating matchup data. A genuine
generation change receives a new family; do not add generation conditionals to the
calculator or renderer.

Item IDs may map to different item-data archive members. Engine adapters should
decode that mapping from the ROM rather than assuming an item ID is also an
archive index. The Generation IV adapter locates and validates the complete ARM9
mapping table, allowing hacks to repurpose unused item IDs without profile-level
member overrides.

## 3. Implement or extend the platform and engine

For a new platform, add container and filesystem readers under
`src/romwiki/platforms/<platform>/`. Validate offsets, sizes, and archive bounds
before exposing data to an engine. Register the platform's image inspector,
filesystem/archive types, and header-matching function as a new entry in
`src/romwiki/platforms/registry.py`'s `_PLATFORMS` dict, and give the profile a
matching `platform` key.

Add engine parsers under `src/romwiki/engines/<engine>/` for each supported record
type. Keep parsers small, typed, and independently testable. Preserve raw source
locations in provenance and reject malformed or out-of-range records instead of
silently guessing. Register the new engine's modules as a new `EngineAdapter` entry
in `src/romwiki/engines/registry.py`'s `_ENGINES` dict; pipeline modules resolve
parsers and constants through `get_engine(profile.engine)` rather than importing an
engine package directly, so this registration is what makes an existing pipeline
module's extraction and enrichment logic *dispatch* to the new engine. Extend
`tests/engines/test_contract.py`'s fake-engine coverage if the new engine exercises
a shared code path the fake engine doesn't yet cover.

Registration alone is not always the *only* change needed, though. A pipeline
module that has only ever been exercised by one engine can carry that engine's
unstated assumptions — invisible until a second real engine hits the same code
path. Implementing `gen5_bw` found two: `pipeline/locations.py` unconditionally
required several Platinum-only Sinnoh mechanics (honey trees, Trophy Garden,
Great Marsh, decorations, seals, Battle Frontier), and `pipeline/build_context.py`
eagerly required several ancillary Pokémon-enrichment datasets (learnsets,
evolutions, machines, tutors, egg moves, pickup) that a new engine's first
vertical slice may not have implemented yet. Both needed a small, targeted fix —
gate the feature on whether the profile actually configures it (`"x" not in
profile.layout` / `profile.parameters`, mirroring `pipeline/reference_names.py`'s
existing pattern), returning `None`/skipping cleanly rather than raising. Expect
to audit pipeline modules your new engine's slice actually exercises for this
kind of single-engine assumption, not just add the registry entry.

For a hack-specific change, prefer a documented format variant shared through the
engine over a parser named after one hack.

## 4. Emit normalized datasets

Add an adapter or pipeline that maps engine records into the schemas under
`src/romwiki/schema/`. Reuse semantic fields and IDs already consumed by enrichment
and rendering.

Trainer party formats require an engine translator under
`src/romwiki/engines/<engine>/trainer_party.py`. Register it in
`pipeline/trainer_party.py` and emit the shared contract from
`schema/trainers.py`. Do not teach the shared trainer renderer about a generation's
difficulty byte, PID algorithm, ability flags, or EV defaults. Preserve those raw
inputs under `source_fields`, expose their semantic result through the canonical
fields, and attach `stored`, `derived`, or `engine-default` provenance. Mark move
behavior as `explicit`, `level-up`, or `unavailable`, and increment
`TRAINER_PARTY_SCHEMA_VERSION` for a breaking party-contract change.

If party pages expose calculated stats, implement the generation's formula in its
engine adapter and emit normalized `calculated_stats`; do not calculate them in a
renderer. This keeps DV/Stat Experience generations separate from IV/EV formulas.

When a mechanic depends on an engine table outside the party record, expose its
location through the game profile. For D/P/Pt, `trainer_class_gender_offset`
locates the ARM9 class-gender table used by deterministic trainer Pokémon PIDs.
Exact trainer prize money follows the same boundary. The engine parser should
decode its stored multiplier and provenance, while the shared reward pipeline
calculates the normalized payout. For the supported D/P/Pt layout, profiles locate
the class multiplier table with:

```toml
[parameters]
trainer_class_prize_overlay_id = 16
trainer_class_prize_offset = 0x359E0
```

Only configure verified locations for the exact ROM revision. Do not infer
multipliers from trainer class names, and keep AI battle items and post-victory
items separate from money rewards.

At minimum, each dataset should include:

- `schema_version`;
- the stable game/profile identifier;
- record and audit counts;
- source metadata;
- normalized records with provenance where practical.

Extend a schema only for a real cross-game concept. New fields should be optional
when older games cannot supply them, and a breaking semantic change requires a
schema-version change.

## 5. Configure enrichment

Provide the matching PokéDB generation output when the wiki needs canonical names,
slugs, or links. Add mappings for engine-local identifiers only where the mapping is
stable and testable. ROM-derived mechanics remain authoritative.

## 6. Add the site

Create:

```text
sites/games/<game-id>/
|-- game.toml
|-- mkdocs.yml
`-- wiki/
    |-- index.md
    `-- data-sources.md
```

Register the profile in `game.toml`, choose a stable URL slug, and document the
exact input version and extraction limitations in `data-sources.md`.

Every game descriptor also provides the portal and shared frontend metadata:

```toml
[site]
id = "renegade-platinum"
name = "Pokémon Renegade Platinum"
kind = "game"
slug = "renegade-platinum"
published = true
order = 10
mkdocs_config = "mkdocs.yml"
description = "An exact, data-driven reference for Pokémon Renegade Platinum"

[game]
profile = "renegade-platinum"
generation = 4
base_game = "platinum"
platform = "nintendo-ds"
platform_name = "Nintendo DS"
creator = "Drayano"

[appearance]
theme = "platinum"
```

IDs, platform names, and theme tokens use lowercase hyphenated values. Add the
theme token's CSS variables to the shared stylesheet only when the existing palette
is unsuitable. Do not create a game-specific copy of the shared templates.

The game MkDocs configuration inherits `sites/shared/mkdocs.base.yml`, points
`theme.custom_dir` at the shared overrides, and registers the repository-local
MkDocs hook. Copy the relative-path pattern from the existing game site.

Documentation-only sites may set `data_driven = false` in `[game]` and omit
`profile`/`profiles`. They remain first-class catalog and deployment entries but
skip generated-data snapshot validation and data-section cards. Add real profiles
and remove the flag when ROM extraction support is ready.

Renderers should emit the current catalog schema version beside each supported
section index. Catalog records contain only the fields needed for browsing and
filtering; the normalized dataset remains authoritative. Preserve a complete
Markdown link fallback so new categories remain usable without JavaScript.

### Sibling game versions (e.g. Black/White)

Two or more releases of the same game (same engine, data confirmed identical
except for version-exclusive records or explicitly supported same-key variants)
may publish as **one** site. Each release still gets its own `GameProfile` under
`profiles/games/` (needed to hash-match its own ROM), but the site descriptor's
`[game]` table lists both under `profiles = ["black-us", "white-us"]` instead of
a single `profile`, and there is no `sites/games/black-us/` or `.../white-us/`
directory at all -- only `sites/games/black-white/`.

The descriptor must also provide one stable lowercase-hyphenated version label per
profile in the same order:

```toml
[game]
profiles = ["black-us", "white-us"]
versions = ["black", "white"]
```

The catalog-driven `romwiki regenerate` command uses these labels directly; it
does not infer user-facing version identity from profile IDs.

The `romwiki build-version-family --games black-us white-us --versions black
white --site-id black-white` command accepts two or more profiles, merges each section with
`pipeline.version_merge.merge_version_family_datasets` (which tags every record with
the `versions` it appears in -- `["black", "white"]` for shared content, a
single entry for an exclusive), and renders the merged dataset into that one
site. Renderers surface a "Black only"/"White only" callout automatically via
`components.version_availability_note` whenever a record's `versions` list has
exactly one entry; shared records get no callout. Do not use this pattern for
a ROM hack and its base game (e.g. Renegade Platinum vs. Platinum) -- those are
deliberately different games and keep their existing separate-sites-plus-
comparison-diff treatment (`pipeline.comparisons`).

When the two sibling profiles are themselves a paired hack, define `base_rom`
for both local game registrations. The same command then compares each hack
with its corresponding clean base and merges those results with
`merge_version_comparisons`. Detail pages preserve separate per-version
comparisons wherever their values differ. Both registrations must define a
base or neither may do so; a half-configured paired comparison is rejected.
`--site-id` is required by the preferred command, preventing a new family from
accidentally overwriting an existing site. `build-version-pair` remains as a
compatibility alias and retains its historical `black-white` default.

Same-key records whose current values differ retain all complete records under
`version_variants`. Only dataset kinds registered as variant-capable may contain
them; merging fails rather than silently publishing the first value when a
renderer lacks that support. The Generation V encounter and item renderers are
the current examples for version-specific encounter tables and NPC trade
references.

## 7. Validate before publication

- Add unit tests for every new binary record and script parser.
- Add profile identification tests for supported hashes and rejection tests for
  near matches.
- Add normalized contract and renderer tests.
- Test explicit type-chart selection and any hack overrides, including single- and
  dual-type defensive calculations, immunities, and fractional multipliers.
- For trainer support, test explicit/default move provenance, unavailable optional
  attributes, engine-derived attributes, exact reward inputs, and resolution
  against the game's own Pokémon dataset.
- Test presentation relationships independently for forms, sibling versions,
  deterministic ordering, deduplication, and absent optional datasets.
- Add baseline-versus-hack comparison fixtures for every supported dataset.
- Extract the complete target and reconcile record counts against its archives.
- Manually verify representative records from every content category.
- Run the full test suite and build the individual site and combined Pages artifact.
- Run `romwiki site snapshot` after validating the complete generated output,
  then test `romwiki site restore-snapshot` from a clean checkout.
- Run `romwiki regenerate --all` to verify the descriptor-driven complete workflow.
- Run `romwiki build-game --game <id>` twice and confirm the second run reuses the
  baseline cache.
- Test catalogs with missing optional values, duplicate labels, and enough records
  to exercise progressive rendering.
- Review representative pages at desktop and narrow mobile widths in light and dark
  modes, including sprite and catalog failure fallbacks.
- Confirm no ROM, patch, key, save, or copyrighted extracted asset is tracked.

See [Frontend](frontend.md) for the shared component and catalog contracts.

## Recommended implementation order

Implement one vertical slice first: identification, a small engine parser, a
normalized dataset, and a rendered page. Pokémon personal data is usually a useful
first slice because it exercises IDs, external name resolution, schema mapping, and
rendering without requiring map-script control-flow analysis.

After that slice proves the adapter boundary, add moves, learnsets and evolutions,
encounters, trainers, and locations incrementally. A game can publish partial
coverage as long as the site states that coverage precisely.

# Adding a game

The amount of work depends on how closely the new game matches an already supported
platform and engine. Begin by classifying the target before writing parsers.

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

Keep format logic out of the profile. A profile should select and configure a
parser, not implement one through a large collection of magic values.

When PokéDB contains generation-specific sprites, set the optional reference key:

```toml
[reference]
sprite_version = "platinum"
```

Use the exact key present under PokéDB's `sprites.versions`. If it is absent or its
URL is unavailable, rendered pages use PokéDB's generic front sprite and then a
text-only fallback. Sprite availability must never affect extraction success.

When a hack repurposes an engine-local identifier, declare the semantic override
in its profile instead of changing the engine default. For example, a Generation
IV hack that uses the otherwise unknown type ID 9 for Fairy declares:

```toml
[semantics.types]
9 = "fairy"
```

Type names must be lowercase hyphenated values. Enrichment applies the override to
every normalized Pokémon and move type while an unconfigured Generation IV game
continues to use the engine's standard mapping.

Replaced moves use the same mechanism so their names and links remain consistent
in move records, learnsets, trainer parties, machines, tutors, egg moves, and
evolution conditions:

```toml
[semantics.moves]
66 = "play-rough"
```

## 3. Implement or extend the platform and engine

For a new platform, add container and filesystem readers under
`src/romwiki/platforms/<platform>/`. Validate offsets, sizes, and archive bounds
before exposing data to an engine.

Add engine parsers under `src/romwiki/engines/<engine>/` for each supported record
type. Keep parsers small, typed, and independently testable. Preserve raw source
locations in provenance and reject malformed or out-of-range records instead of
silently guessing.

For a hack-specific change, prefer a documented format variant shared through the
engine over a parser named after one hack.

## 4. Emit normalized datasets

Add an adapter or pipeline that maps engine records into the schemas under
`src/romwiki/schema/`. Reuse semantic fields and IDs already consumed by enrichment
and rendering.

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
name = "Renegade Platinum"
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

Renderers should emit a `schema_version: 1` catalog beside each supported section
index. Catalog records contain only the fields needed for browsing and filtering;
the normalized dataset remains authoritative. Preserve a complete Markdown link
fallback so new categories remain usable without JavaScript.

## 7. Validate before publication

- Add unit tests for every new binary record and script parser.
- Add profile identification tests for supported hashes and rejection tests for
  near matches.
- Add normalized contract and renderer tests.
- Extract the complete target and reconcile record counts against its archives.
- Manually verify representative records from every content category.
- Run the full test suite and build the individual site and combined Pages artifact.
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

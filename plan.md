# Blaze Black 2 Redux and Volt White 2 Redux Plan

## Goal

Add ROM-derived support for the locally supplied Complete-mode Redux releases as
a separate sibling-version site, while reusing the existing Black 2/White 2
engine and preserving the original Blaze Black 2/Volt White 2 v1.1 site.

## Known inputs

- Blaze Black 2 Redux Complete
  - Game code: `IREO`
  - SHA-256: `332d07576e2077b4ef91e394603d144108098b7624c6a918b175f90530c0036a`
- Volt White 2 Redux Complete
  - Game code: `IRDO`
  - SHA-256: `cf75c45ef07596e31f9d5bf4babde67b60a028e6b85eb811c14a7d4715a21120`
- Clean comparison ROMs: the existing `black-2-us` and `white-2-us` inputs.
- Both Redux ROMs retain the standard 662-file B2W2 filesystem, but their code
  binaries differ from retail and require offset-sensitive features to be
  verified.

## Work plan

### 1. Establish exact release metadata

- [x] Confirm the Redux release version represented by both ROMs and use one
  consistent variant label in profiles and documentation.
- [x] Confirm that both inputs are Complete-mode counterparts from the same
  release.

### 2. Add profiles and local registration

- [x] Add `blaze-black-2-redux` and `volt-white-2-redux` hack profiles.
- [x] Extend the matching retail B2W2 profiles and override only verified Redux
  differences.
- [x] Register the exact hashes above and explicitly select the Generation V
  type chart.
- [x] Add both games and their clean base ROMs to `.local/games.toml` and the
  path-only examples to `config/games.example.toml`.
- [x] Add profile tests covering inheritance, release metadata, exact hash
  matching, and near-match rejection.

### 3. Verify engine compatibility

- [x] Run focused extraction for each Redux ROM using the existing `gen5_b2w2`
  engine.
- [x] Validate every enabled dataset: Pokémon, abilities, moves, items,
  encounters, trainers, and locations.
- [x] Verify archive paths, message members, form handling, script parsing,
  static encounters, shops, trades, pickup data, and tutor data.
- [x] Recalculate or replace fixed offsets where Redux code changes invalidate
  inherited retail values; prefer existing pattern-based discovery when
  appropriate.
- [x] Add only the compatibility flags or engine changes demonstrated necessary
  by extraction failures.
- [x] Add focused regression tests for every new parser behavior or Redux-specific
  profile override.

### 4. Add the Redux sibling-version site

- [x] Create a distinct `blaze-black-2-redux-volt-white-2-redux` site so the
  original v1.1 site remains available.
- [x] Configure both Redux profiles and version labels in deterministic Black/White
  order, using `black-2-white-2` as the clean base-game family.
- [x] Add concise site metadata, navigation, data-source notes, and representative
  development pages following the existing B2W2 sites.
- [x] Add release documentation that can be distributed legally; do not commit
  ROMs, patches, or copyrighted extracted assets.
- [x] Add or update catalog and documentation tests for the new site.

### 5. Generate and review only the new site

- [x] Run targeted Redux regeneration during development; do not regenerate
  unrelated sites.
- [x] Confirm clean-ROM baseline caches are reused and a second incremental run
  skips unchanged extraction and rendering work.
- [x] Reconcile record counts and version variants, then manually review
  representative pages from every generated section.
- [x] Audit the built site and verify links, data downloads, comparisons, and
  responsive presentation.

### 6. Final validation and publication state

- [x] Run formatting, linting, relevant tests, and then the full test suite.
- [x] Build the combined Pages artifact to verify portal and deployment
  integration.
- [x] Update only the new/changed generated-wiki snapshot archives and manifest.
- [x] Restore the snapshot and audit it to verify a clean-checkout workflow.
- [x] Confirm the working tree contains no local ROM paths or prohibited assets.
- [x] Update `README.md`, the adding-a-game documentation, and any supported-site
  listings affected by the addition.

## Completion criteria

The work is complete when both exact Redux ROMs are identified, every advertised
dataset extracts and renders correctly against its clean sibling baseline, the
new site passes audit and full repository validation, incremental reruns reuse
unchanged work, documentation matches the implemented workflow, and the ROM-free
snapshot can reproduce the published content.

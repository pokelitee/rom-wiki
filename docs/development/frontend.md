# Frontend

ROM Wiki uses one shared MkDocs Material frontend for the portal and all game
sites. Game sites configure identity and content; they do not fork templates or
styles.

## Shared layers

`sites/shared/mkdocs.base.yml` owns common Material features, palettes, plugins,
and Markdown extensions. Each site inherits that file and points at
`sites/shared/overrides/` for templates and assets.

Material instant navigation is intentionally disabled. The combined artifact is
made up of independently built MkDocs applications, each with its own theme
metadata, JavaScript state, and search index. Crossing a wiki boundary must load
the complete target document so those site-specific resources are initialized
correctly.

The repository-local MkDocs hook reads the existing site catalog for every build
and adds the current site, portal URL, and published games to template context. It
calculates links from each page depth, so navigation works both with `mkdocs serve`
and when the combined artifact is hosted below a GitHub Pages repository path.

Appearance tokens are declared in every site descriptor's `[appearance]` table,
including the portal. Shared CSS maps a token to custom properties such as
`--rw-accent`; components consume the variables rather than game names. Components
must support the default and slate Material schemes and remain readable without
color.

Each published theme defines light and dark values for its accent, filled accent,
surfaces, borders, muted text, and shadows. The portal applies the same tokens to
game cards so their visual identity is visible before entering a game site.
Material owns the active color-scheme attribute on the document body; shared
selectors combine that body state with the site token on the document root. The
head template applies site identity before loading CSS and synchronizes an explicit
light/dark choice across the independently built wiki roots.

Use `--rw-accent` for foreground text, borders, and decorative fills.
Controls with text or icons on a solid theme-colored background use
`--rw-accent-strong` with `--rw-on-accent`.

`theme.css` also defines a fixed set of custom properties independent of any
game's appearance token: `--rw-positive`/`--rw-negative` for change-status
colors and `--rw-gender-male`/`--rw-gender-female` for gender indicators, each
with separate light- and dark-mode values verified for WCAG AA contrast
against `--rw-surface`, plus `--rw-select-chevron`/`--rw-select-chevron-inverse`
for the shared dropdown icon. Components reference these directly rather than
redefining colors locally.

The shared `404.html` provides portal- and game-aware recovery links. GitHub Pages
builds pass the deployment root through `ROMWIKI_SITE_URL`; the MkDocs hook derives
each site's `site_url` from it so 404 assets and links remain valid when the combined
artifact is hosted below a repository path. Local builds may leave it unset.

Shared frontend assets are divided by responsibility. `theme.css` owns tokens,
Material integration, and global scrolling; `shell.css` owns navigation and landing
pages; `records.css` owns shared record primitives; `party.css`,
`comparisons.css`, and `record-visuals.css` own their larger component families;
`controls.css` owns reusable select and combobox presentation; and `catalog.css`
owns catalog layout and tables. Keep responsive rules with the component they
modify. The template loads these as separate stylesheets rather than chaining CSS
imports.

`romwiki.js` is a small browser-module entry point. Site-wide behavior lives in
`site.js`, reusable field behavior in `controls.js`, and display normalization in
`formatting.js`. The `catalog/` modules separately own the catalog contract,
renderers, and interactive orchestration. Modules may depend toward these lower
layers, but shared controls and formatting must not depend on catalog definitions.
This structure is shared by every game; do not create game-specific frontend
bundles for normalized data or appearance differences.

## Optional-section policy

Render a section with an explicit empty state when the mechanic exists for the
game but this record has no entries. Omit the section when the dataset's
`features` contract says the mechanic does not exist for that game. Summary and
hero facts follow the same rule: stable core facts may show `None`, while
generation-specific facts appear only when supported. This keeps page geometry
predictable without presenting an absent mechanic as missing extraction.

## Catalog contract

Each generated section writes `catalog.json` with this envelope:

```json
{"schema_version":2,"kind":"pokemon","records":[]}
```

The `kind` selects the shared filters, columns, and sorting behavior. Every record
has a stable ID, display label, final directory URL, and normalized `search_text`.
Section-specific fields provide only the values visible, searchable, sortable,
or filterable in the catalog. Catalog definitions may use select or searchable
combobox facets, numeric ranges, sort direction, and correlations between facets.
Comparative builds add a shared `change_status` field, filter, and badge column to
every section; section configurations must not reimplement that common control.
Comparison presentation is field-aware. Pokémon pages show ability slots,
compatibility changes, grouped learnset differences, and individual stat changes
as readable labels. Generic structured changes lead with a short human summary and
place exact normalized JSON in a collapsed audit detail instead of using raw JSON
as the primary interface.
For example, encounter records preserve the Pokémon available through each method
so combining those filters cannot produce a false match. Breaking catalog changes
require a version bump and matching JavaScript support.

Entity relationships remain ID-based in normalized data. Renderers convert them
to additive catalog references with `kind`, `id`, `label`, and an optional resolved
`url`; existing scalar fields remain available for filtering. Catalog columns render
the reference as a link only when `url` is present, so an unresolved relationship
cannot create a guessed or broken target.

`renderers/mkdocs/references.py` is the single route registry for cross-entity
links. It resolves Markdown source paths separately from published directory URLs
and accounts for the source page depth. Catalog JSON and detail-page renderers must
use this resolver instead of constructing section paths from labels or slugs.

Full game builds also create a reference index from the generated datasets. The
index maps stable normalized IDs to the route keys of pages that actually exist.
This lets location pickups, shop inventory, gifts, trades, static encounters, and
held items link to their item or Pokémon pages without deriving a slug from display
text. A missing route remains visible as plain text. Tutor location list positions
are not map-header IDs, so tutor locations remain unlinked until a profile supplies
an explicit map-header identity.

A separate presentation relationship index derives approved reverse joins once per
build. Pokémon availability and trainer appearances, level-up and machine learners,
and Generation V location-to-encounter links all consume this shared index.
Catalog-only metrics such as obtainability, encounter-location counts, minimum
known obtainable level, trainer appearances, and learner counts must be derived
from it rather than from page-specific dataset scans.

Multi-select facets are reserved for fields where each record can contain several
values. They remain open while options are toggled and default to matching every
selected value. Once two values are selected, users can switch that facet between
`All` and `Any`; non-default modes use a companion query parameter such as
`types_mode=any`. Selections use repeated query parameters. Scalar facets and
high-cardinality searchable comboboxes remain single-value controls. Comboboxes
accept free text, limit the rendered suggestion list, and preserve substring
matching so users do not have to choose an exact suggestion.

The index contains a `data-rw-catalog` container followed by every record as normal
Markdown links. JavaScript hides that fallback only after it has successfully
started, preventing it from flashing before the interactive catalog renders. A
loading indicator occupies the catalog region in the meantime. The fallback stays
visible without JavaScript and is restored if the catalog cannot load or validate.
Filtering and sorting happen locally, 50 rows render at a time, and non-default
controls are stored in the query string. Player-facing tables should lead with
recognizable game data; internal IDs should be combined or moved later in the row
when they distinguish otherwise identical records.

Do not put sprites in catalog rows. Hundreds of external image requests would make
indexes slower and less reliable.

## Development preview

Use the combined development server when changing shared templates, styles, or
behavior across the portal and game sites:

```console
romwiki site serve --all --dev
```

It builds one artifact below `build/mkdocs-dev/`, uses every game's lightweight
configuration, watches shared and site sources, and reloads open browser pages
after successful rebuilds. The portal uses its normal configuration because its
source is already small.

Use the same command with one or more site identifiers for a focused preview:

```console
romwiki site serve renegade-platinum --dev
romwiki site serve platinum renegade-platinum --dev
```

The server replaces its output directory at startup so a focused preview cannot
serve stale sites left by an earlier combined build. A single game redirects the
root request to that game's path.

Use the lightweight Renegade Platinum configuration while iterating on shared
templates, styles, and catalog behavior:

```console
python -m mkdocs serve --dirty --config-file sites/games/renegade-platinum/mkdocs.dev.yml
```

It inherits the production configuration, keeps every catalog index and JSON
payload, and includes one representative detail page from each generated section.
The remaining generated Markdown pages are excluded, and development output is
written below `build/mkdocs-dev/`. Link validation for excluded detail pages is
disabled only in this configuration.

Always use the production configuration or the multi-site build before deployment.
The deploy workflow runs the unit suite, builds each published site concurrently,
merges their artifacts, and audits the combined result. Run the same artifact
checks locally with:

```console
romwiki site build --all --output dist
romwiki site audit dist
```

The audit validates local links and fragments, document landmarks and headings,
image alternatives and loading behavior, table and disclosure semantics, custom
CSS usage, and conservative page-size and image-count budgets. It operates on the
combined artifact so portal links and links between independently built game sites
are resolved in their deployment context.

`tests/sites/test_frontend_contract.py` provides a browser-independent visual contract
for the shared palettes, focus treatment, reduced-motion behavior, responsive
breakpoint, and dense party-card layout. Renderer tests cover the corresponding
semantic markup. This keeps layout regressions deterministic in CI; manual review
at the two documented viewport classes remains appropriate for changes whose
appearance depends on browser font rasterization.

## Record components

Renderer helpers produce semantic classes for type badges, summaries, stat bars,
fact grids, exact clean-ROM comparisons, compact link lists, party cards, record
navigation, and provenance details. Exact numeric values and normal links remain
in the document; visualization is supplementary. Type badges are presentational
labels rather than links. The complete type chart remains available through site
navigation, and its row and column labels are plain text because they do not lead
to distinct content. Pokémon detail pages place their defensive effectiveness
summary after base stats, then group move sources under one learnset section and
include the common type, class, power, accuracy, and PP fields alongside
source-specific level, machine, location, and requirement columns. Evolution
sections derive a complete branch-aware graph from the ROM evolution dataset,
stack wide branches into readable rows, make each species card navigable,
highlight the current record, and guard against cycles. Long chains retain
horizontal overflow as a narrow-viewport fallback. Branch outcomes remain separate
horizontal paths so multi-stage lineage stays unambiguous. The lightweight
development build retains Eevee and Wurmple as representative branch-layout
fixtures.

Pokémon sprites are optional external URLs selected during enrichment. The summary
uses one default image and the detail gallery includes all available version-specific
front/back, normal/shiny, and gender variants. Pages use lazy loading, an explicit
source link, and a visible fallback after load failure. The build must not download
or copy sprites.

The "do not put sprites in catalog rows" rule above applies to the large,
paginated `catalog.json`-driven tables only. A small, single-record detail
page's own bounded sub-table — an ability's assigned-Pokémon list, one wild
encounter area's per-method slot table, one trainer's party cards — has at
most a few dozen rows and renders a shared `table_sprite_cell()` icon column;
this is a deliberate exception, not an inconsistency with the catalog rule.

Trainer party cards consume only normalized data. They show each Pokémon's sprite
and, when the slot has one, the held item's icon. Explicit moves retain their stored
order in a numbered list; `level-up` moves render as a distinct default-moves
state rather than a numbered move. Optional ability, nature, gender, IV, and EV
fields must be omitted cleanly when an engine cannot provide them. Renderer code
must never derive those mechanics from raw engine fields. Cards group level,
nature, and gender into one identity line, use a compact aligned list for ability
and held item, and show final stats, IVs, and EVs in a six-column stat matrix.

Trainers also carry an "AI battle items" summary and, when populated, detail
section: the ROM's
4-slot `reward_item_ids` array holds items the trainer's own AI may use on its
party mid-battle (Full Restores, X-stat items), never a reward for the player,
so the field and its UI are both named for what it actually is. Gen V trainers
may separately expose a post-victory party heal and an item given to the player.
Those are normalized as `healer` and `victory_item`; item pages invert the latter
into trainer-reward backlinks. Wild encounter
slot tables show a per-slot catch-rate percentage from the fixed Generation
III/IV engine weight tables (not ROM data) and combine slots that share a
species and level(s) into one row with their chances summed, since the ROM
encodes higher odds by repeating a species across more slots rather than
storing a percentage.

Genus, measurements, and a version-matched Pokédex entry may come from PokéDB.
These are labeled reference content. Stat, type, ability, training, breeding,
evolution, held-item, and learnset values shown for the hack remain ROM-derived.

Raw HTML links use final directory URLs because MkDocs does not rewrite `.md` paths
inside HTML. Normal Markdown links use source filenames so MkDocs can validate and
rewrite them. Both forms must resolve through the shared route registry; the output
syntax follows the surrounding component rather than defining link identity.

## Review checklist

- Run the unit suite and `romwiki site audit` against the combined artifact.
- Test keyboard focus, labels, and the live catalog result count.
- Verify the full index remains usable when JavaScript is disabled.
- Verify failed catalog and sprite requests reveal their fallbacks.
- Review both palettes at desktop and narrow mobile widths.
- Build the portal, one game, and the combined Pages artifact.

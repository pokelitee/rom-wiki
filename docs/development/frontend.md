# Frontend

ROM Wiki uses one shared MkDocs Material frontend for the portal and all game
sites. Game sites configure identity and content; they do not fork templates or
styles.

## Shared layers

`sites/shared/mkdocs.base.yml` owns common Material features, palettes, plugins,
and Markdown extensions. Each site inherits that file and points at
`sites/shared/overrides/` for templates and assets.

The repository-local MkDocs hook reads the existing site catalog for every build
and adds the current site, portal URL, and published games to template context. It
calculates links from each page depth, so navigation works both with `mkdocs serve`
and when the combined artifact is hosted below a GitHub Pages repository path.

Appearance tokens are declared in a game's `[appearance]` table. Shared CSS maps a
token to custom properties such as `--rw-accent`; components consume the variables
rather than game names. Components must support the default and slate Material
schemes and remain readable without color.

## Catalog contract

Each generated section writes `catalog.json` with this envelope:

```json
{"schema_version":1,"kind":"pokemon","records":[]}
```

The `kind` selects the shared filters, columns, and sorting behavior. Every record
has a stable ID, display label, final directory URL, and normalized `search_text`.
Section-specific fields provide only the values visible, searchable, sortable,
or filterable in the catalog. Catalog definitions may use select or searchable
datalist facets, numeric ranges, sort direction, and correlations between facets.
For example, encounter records preserve the Pokémon available through each method
so combining those filters cannot produce a false match. Breaking catalog changes
require a version bump and matching JavaScript support.

The index contains a `data-rw-catalog` container followed by every record as normal
Markdown links. JavaScript hides that fallback only after it has successfully
loaded and validated the JSON. Filtering and sorting happen locally, 50 rows render
at a time, and non-default controls are stored in the query string. Player-facing
tables should lead with recognizable game data; internal IDs should be combined or
moved later in the row when they distinguish otherwise identical records.

Do not put sprites in catalog rows. Hundreds of external image requests would make
indexes slower and less reliable.

## Development preview

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

## Record components

Renderer helpers produce semantic classes for type badges, summaries, stat bars,
party cards, record navigation, and provenance details. Exact numeric values and
normal links remain in the document; visualization is supplementary.

Pokémon sprites are optional external URLs selected during enrichment. Pages use
lazy loading, an explicit source link, and a visible fallback after load failure.
The build must not download or copy sprites.

Raw HTML links use final directory URLs because MkDocs does not rewrite `.md` paths
inside HTML. Normal Markdown links may continue to use source filenames.

## Review checklist

- Test keyboard focus, labels, and the live catalog result count.
- Verify the full index remains usable when JavaScript is disabled.
- Verify failed catalog and sprite requests reveal their fallbacks.
- Review both palettes at desktop and narrow mobile widths.
- Build the portal, one game, and the combined Pages artifact.

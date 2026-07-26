# Data contracts

ROM Wiki has three publication layers with different responsibilities:

- Detail Markdown is curated for people. It presents every supported mechanic
  that is useful on the page, but does not mirror normalized JSON field-for-field.
- `catalog.json` is a compact, versioned presentation index used by the local
  filters and static fallback. It is not a bulk-data API.
- `data/*.json.gz` contains the complete normalized datasets used by renderers,
  including ROM facts, provenance, relationships, and PokéDB reference objects.
  Comparative sites also publish `data/comparisons/*.json.gz`.

Every dataset envelope contains a dataset name, game identity, schema version,
record count, source metadata, records, and a sorted `features` list. A feature
means the exact engine/profile combination supports that mechanic. Record-level
emptiness is separate: an empty list means the mechanic exists but this record
has no entries.

## Compatibility

Schema constants live in `src/romwiki/schema/versions.py`. Increment the affected
raw or enriched schema whenever a serialized field changes meaning, shape, or
required presence. Do not invalidate unrelated datasets.

Sibling-version merging requires the same dataset kind, schema version, and
feature contract on every side. Differing current records are retained only for
dataset kinds whose renderers explicitly support version variants.

## Public downloads

The data exporter serializes canonical compact UTF-8 JSON and writes deterministic
gzip archives. `data/manifest.json` lists every archive with its schema version,
record count, compressed byte size, and SHA-256 checksum. Snapshot validation
decompresses and parses each archive and verifies its checksum, so publication
cannot silently ship missing or corrupt data.

The archives never contain ROM or patch bytes. External reference fields remain
labeled as PokéDB-derived; exact mechanics and comparisons remain ROM-derived.

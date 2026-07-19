# Methodology

Wiki data is decoded from locally supplied game images, normalized into structured
records, validated, and rendered as static documentation. Published data records
its source and confidence where possible.

The extraction layer is game-aware, but the normalized records and wiki renderer
are not intended to depend on ROM offsets, archive formats, or script opcodes.
This allows games from different engines to share page templates whenever they
can supply the same normalized concepts. Engine-specific facts remain available
as provenance or optional fields instead of leaking into the presentation layer.

Game images, patches, saves, and extracted copyrighted assets are not published.

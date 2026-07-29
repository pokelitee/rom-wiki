# Data sources

## Primary ROMs

- Pokémon Black (USA): header code `IRBO`, ROM version 0, SHA-256
  `b9979189d299a0231d01c8885c0d054b706976ffc75427ca59d84e0ce1493034`.
- Pokémon White (USA): header code `IRAO`, ROM version 0, SHA-256
  `b288bb061fd646894f5059f55cd0a1efb13b4f0cfd3d9e06e9e42a5bd9431ac6`.

## Publication model

Black and White are published as one paired retail reference. Both ROMs are
parsed independently and merged by stable record identity. Shared records
appear once, while differing encounters, trades, and other version-specific
records retain explicit Black and White sections.

## Coverage and provenance

The wiki derives Pokémon, abilities, items, moves, the type chart, wild
encounters, trainers, and locations directly from the ROMs. PokéDB supplies
reference names, descriptions, links, and sprites; it is not used as a
mechanics baseline.

## Engine notes

Black and White use the Generation V Black/White engine (`gen5_bw`).

The sections below describe the shared Generation V Black/White engine record
formats and decoding techniques.

--8<-- "gen5-bw-data-sources.md"

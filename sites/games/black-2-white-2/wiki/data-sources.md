# Data sources

## Primary ROMs

- Pokémon Black Version 2 (USA/Europe): header code `IREO`, ROM version 0,
  SHA-256
  `2e6b2415354aa41471bc7617068dce059a59931bf5c4348a264f8043f297683a`.
- Pokémon White Version 2 (USA/Europe): header code `IRDO`, ROM version 0,
  SHA-256
  `3e50aec3db401332175a5d2b5fe2a68ac1a05ec63995dba9d1506b1b51837446`.

## Publication model

Black 2 and White 2 are published as one paired retail reference. Both ROMs
are parsed independently and merged by stable record identity. Shared records
appear once, while differing encounters and other version-specific records
retain explicit Black 2 and White 2 sections.

## Coverage and provenance

The wiki derives Pokémon, abilities, items, moves, the type chart, wild
encounters, trainers, and locations directly from the ROMs. PokéDB supplies
reference names, descriptions, links, and sprites; it is not used as a
mechanics baseline.

## Engine notes

Black 2 and White 2 use the shared Generation V parsers where their binary
formats match Black and White, with a dedicated B2W2 engine layer for personal
record size, alternate-form members, Pokéstar Studios records, item field-use
IDs, archive bounds, and other sequel-specific constants.

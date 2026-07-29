# Data sources

The primary sources are the exact USA/Europe NDSi-Enhanced releases of Pokémon
Black Version 2 (header code `IREO`, ROM version 0) and Pokémon White Version 2
(header code `IRDO`, ROM version 0).

- Black 2 SHA-256:
  `2e6b2415354aa41471bc7617068dce059a59931bf5c4348a264f8043f297683a`
- White 2 SHA-256:
  `3e50aec3db401332175a5d2b5fe2a68ac1a05ec63995dba9d1506b1b51837446`

Both versions are parsed independently and merged by stable record identity.
Shared records appear once, while differing encounters and other
version-specific records retain explicit Black 2 and White 2 sections.

The wiki derives Pokémon, Abilities, Items, Moves, Wild Encounters, Trainers,
and Locations directly from the ROMs. PokéDB supplies reference names,
descriptions, links, and sprites; it is not used as a mechanics baseline.

Black 2 and White 2 use the shared Generation V parsers where their binary
formats match Black and White, with a dedicated B2W2 engine layer for personal
record size, alternate-form members, Pokéstar Studios records, item field-use
IDs, archive bounds, and other sequel-specific constants.

# Data sources

## Primary ROMs

- Pokémon Blaze Black 2 v1.1 Complete: header code `IREO`, ROM version 0,
  SHA-256
  `f30ba7dcaf3d71f1366737ffe6ceea3c1f584ea220944cb376dfc9d2af950821`.
- Pokémon Volt White 2 v1.1 Complete: header code `IRDO`, ROM version 0,
  SHA-256
  `cb9480a842e86bcef40d069d42a4955a31a1c8850f80c5e62e2151c478f66cf4`.

## Publication model

Blaze Black 2 and Volt White 2 are published as one paired hack reference. Both
patched ROMs are parsed independently and merged by stable record identity.
Shared records appear once, while version-specific records retain explicit
Blaze Black 2 and Volt White 2 sections.

Every supported dataset is compared with its exact retail baseline:

- Blaze Black 2 against Pokémon Black Version 2 (USA/Europe), SHA-256
  `2e6b2415354aa41471bc7617068dce059a59931bf5c4348a264f8043f297683a`.
- Volt White 2 against Pokémon White Version 2 (USA/Europe), SHA-256
  `3e50aec3db401332175a5d2b5fe2a68ac1a05ec63995dba9d1506b1b51837446`.

## Coverage and provenance

The wiki derives Pokémon, abilities, items, moves, the type chart, wild
encounters, trainers, and locations directly from the patched ROMs. PokéDB
supplies reference names, descriptions, links, and sprites; it is not used as a
mechanics baseline.

## Engine notes

The hacks retain the retail B2W2 record formats and use the `gen5_b2w2` engine.
Map headers therefore decode wild-encounter archive indexes from the low twelve
bits of B2W2's flagged field and treat `0xFFF` as null. The profiles select
PokéDB's `black-white` sprite set because that is the available Generation V
reference set; unavailable version-specific images still use the normal generic
fallback.
The v1.1 Complete patcher leaves incorrect declared data-block sizes in the
learnset, field-script, and overworld NARCs, and trailing data in the encounter
NARC. Compatibility for those known archives is enabled only by these hack
profiles; retail and unrelated profiles remain strictly validated.

Three edited personal records contain an invalid secondary egg-group byte.
The hack profiles repair that byte from the valid primary egg group during
normalization. Pokéstar Studios records remain internal, while B2W2 alternate
and battle-only forms retain their sequel-specific identities.

The sections below describe the shared Generation V Black 2/White 2 engine
record formats and decoding techniques.

--8<-- "gen5-b2w2-data-sources.md"

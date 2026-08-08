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

The shared Generation V location pipeline links wild encounter variants in
both directions with their map headers and attaches trainers, warps, outdoor
connections, field items, static encounters, and script-dispatched shops to
location pages. B2W2 shop selectors `0` through `25` resolve to the sequel's
location-specific archive inventories; selectors `253` and `254` resolve BP
exchanges at Gear Station and the PWT, and selector `255` identifies the
standard badge-progression Poké Mart. Fixed NPC trades and the shared fossil
revival are linked through map-owned text/common-script relationships.
Black City's four market stores are also linked directly to the city. Each
store lists its Black Tower unlock requirement, one-item-per-day limit, and
separate weekday and weekend inventory rather than being treated as an
ordinary Poké Mart.

Curtis/Yancy repeat trades are fully decoded and published as Xtransceiver
interactions. They intentionally omit a map link because the trade is mobile
and has no single fixed location. Tornadus and Thundurus are not roaming
encounters in Black 2 or White 2; the ARM-backed roaming limitation applies
only to the original Black and White games.

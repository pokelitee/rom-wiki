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
IDs, archive bounds, and other sequel-specific constants. Their map headers pack
flags into the high four bits of the wild-encounter field, so the engine resolves
encounter archive indexes from the low twelve bits and treats `0xFFF` as the null
value. The profiles select PokéDB's `black-white` sprite set because that is the
available Generation V reference set; unavailable version-specific images still
fall back through the normal generic-sprite policy.

The shared Generation V location pipeline links wild encounter variants in
both directions with their map headers and attaches trainers, warps, outdoor
connections, field items, static encounters, and script-dispatched shops to
location pages. B2W2 shop selectors `0` through `25` resolve to the sequel's
location-specific archive inventories; selector `255` identifies the standard
badge-progression Poké Mart.

## Known coverage limitations

- NPC trades are decoded from the detached trade archive, but their field
  scripts are not yet mapped back to location headers.
- Fossil item-to-species mappings are decoded, but the shared revival script is
  not assigned a map location because it is invoked by another field script
  rather than registered as a map header's dedicated script.

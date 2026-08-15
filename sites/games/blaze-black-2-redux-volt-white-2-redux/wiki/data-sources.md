# Data sources

## Primary ROMs

- Pokémon Blaze Black 2 Redux v1.4.1 Complete: header code `IREO`, ROM
  version 0, SHA-256
  `332d07576e2077b4ef91e394603d144108098b7624c6a918b175f90530c0036a`.
- Pokémon Volt White 2 Redux v1.4.1 Complete: header code `IRDO`, ROM
  version 0, SHA-256
  `cf75c45ef07596e31f9d5bf4babde67b60a028e6b85eb811c14a7d4715a21120`.

## Publication model

Blaze Black 2 Redux and Volt White 2 Redux are published as one paired hack
reference. Both patched ROMs are parsed independently and merged by stable
record identity. Shared records appear once, while version-specific records
retain explicit Blaze Black 2 Redux and Volt White 2 Redux sections.

Every supported dataset is compared with its exact retail baseline:

- Blaze Black 2 Redux against Pokémon Black Version 2 (USA/Europe), SHA-256
  `2e6b2415354aa41471bc7617068dce059a59931bf5c4348a264f8043f297683a`.
- Volt White 2 Redux against Pokémon White Version 2 (USA/Europe), SHA-256
  `3e50aec3db401332175a5d2b5fe2a68ac1a05ec63995dba9d1506b1b51837446`.

## Coverage and provenance

The wiki derives Pokémon, abilities, items, moves, the type chart, wild
encounters, trainers, and locations directly from the patched ROMs. PokéDB
supplies reference names, descriptions, links, and sprites; it is not used as a
mechanics baseline.

## Engine notes

Redux retains the retail B2W2 record formats and uses the `gen5_b2w2` engine.
The profiles enable narrowly scoped compatibility for stale archive and data
block sizes left by the patching tools. Redux's added trainers use a verified
18-byte header variant that omits the normally final victory-item field; the
missing item is normalized as item ID 0.

The developer battles also reference internal Pokéstar Studios actor records,
which are resolved from the ROM's own personal-data archive and remain private to
trainer presentation. One stored Stunfisk party entry uses raw form ID 5 without
a separate personal-data form; the wiki preserves that value as the cosmetic
label `Form 5` rather than inventing mechanics for it.

Redux adds Fairy as type ID 17 and uses the Generation VI Fairy matchups. It
also removes Steel's Generation V resistances to Ghost and Dark. These mechanics
are declared explicitly as sparse profile overrides on the canonical Generation
V chart.

Overworld member 464, associated with Marine Tube, has internally contradictory
record counts in both supported ROMs and cannot be decoded as a B2W2 overworld
record. The Marine Tube location is still published from its valid map header,
but NPC, item, and warp relationships are intentionally omitted for that member.

The Pickup table is located from Redux's edited leading item sequence and
matches the v1.4.1 documentation: Leftovers, Sun Stone, Moon Stone, and King's
Rock entries are replaced by Lucky Egg, Sticky Barb, Lagging Tail, and PP Max.

The profiles select PokéDB's `black-white` sprite set because that is the
available Generation V reference set; unavailable version-specific images use
the normal generic fallback.

The sections below describe the shared Generation V Black 2/White 2 engine
record formats and decoding techniques.

--8<-- "gen5/b2w2-data-sources.md"

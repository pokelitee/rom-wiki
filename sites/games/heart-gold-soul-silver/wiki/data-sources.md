# Data sources

## Primary ROMs

- Pokémon HeartGold (USA): header code `IPKE`, ROM version 0, SHA-256
  `65f02a56842b75aa92d775d56d657a56fe3fa993550b04dc20704ab82d760105`.
- Pokémon SoulSilver (USA): header code `IPGE`, ROM version 0, SHA-256
  `51d0f94a16af7d77c067b4cb7d821ba890a13203a2e2c76049623332c0582e20`.

## Publication model

HeartGold and SoulSilver are modeled as a sibling-version family. Each ROM has
its own identification profile and will be parsed independently before records
are merged by stable identity.

## Coverage and provenance

The executable profile contract currently exposes only the personal-data archive
at `a/0/0/2`. Both retail ROMs contain 508 records of 44 bytes, and the archives
are byte-identical. The normalized Pokémon dataset publishes 505 public species
and battle-form records while retaining three non-public internal records for
audit completeness.

PokéDB supplies names, links, descriptive metadata, and media fallbacks. The ROM
remains authoritative for stats, types, held-item IDs, growth data, abilities,
and TM/HM compatibility flags.

Archive identities are known for moves, items, scripts, messages, learnsets,
evolutions, encounters, map matrices, trainers, egg moves, and NPC trades, but
they are intentionally absent from the executable layout contract. Their HGSS
formats and normalization paths have not yet been verified end to end.

## Engine notes

The distinct `gen4_hgss` leaf adapter supports only the Pokémon dataset. Real
HeartGold, SoulSilver, and Platinum fixtures prove that their personal records
share one Generation IV parser, which lives in shared generation code. HGSS does
not reuse the Platinum adapter: encounter records, map data, scripts, trainers,
items, moves, and ancillary Pokémon data remain unsupported until independently
verified. Unsupported semantic formats are declared explicitly by the adapter.

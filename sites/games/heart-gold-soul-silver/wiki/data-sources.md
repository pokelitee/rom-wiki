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

The initial profiles identify the exact ROMs and locate verified core archives
for Pokémon, moves, items, scripts, messages, learnsets, evolutions, encounters,
trainers, egg moves, and NPC trades. No extracted datasets are published yet.
PokéDB will provide optional reference metadata only, never ROM mechanics.

## Engine notes

The profiles reserve the `gen4_hgss` leaf-engine identifier. HGSS must not reuse
the Platinum-specific `gen4_dppt` adapter wholesale: its archive map, encounter
records, map data, and script behaviors require independent verification. The
site remains non-data-driven and unpublished until that adapter satisfies the
normal extraction and rendering contracts.

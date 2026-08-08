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

The executable profile contract exposes the personal-data archive at `a/0/0/2`
and message archive at `a/0/2/7`. Both retail ROMs contain 508 personal records of
44 bytes, and the archives are byte-identical. The normalized Pokémon dataset
publishes 505 public species and battle-form records while retaining three
non-public internal records for audit completeness.

Message member 720 is byte-identical between the retail versions and contains
exactly 124 ability names, including the internal ID-zero entry. The public
ability dataset emits IDs 1 through 123 and derives Pokémon backlinks solely from
the ROM ability slots in personal records. All 123 abilities have at least one
assignment.

The move archive at `a/0/1/1` contains 471 records of exactly 16 bytes. Both
retail versions are byte-identical, and message member 750 supplies all 468 names
needed for move IDs 0 through 467. The public dataset exposes the 467 playable
moves and retains four non-public internal records for auditing. Move mechanics
include power, type, damage class, accuracy, PP, effect, target, priority, flags,
and contest fields directly decoded from the ROM.

Learnsets, TM/HM move mappings, tutors, and egg moves are not part of this slice.
Move pages therefore publish mechanics but do not claim complete learner or
acquisition relationships.

PokéDB supplies names, links, descriptive metadata, and media fallbacks. The ROM
remains authoritative for stats, types, held-item IDs, growth data, abilities,
and TM/HM compatibility flags.

Archive identities are known for items, scripts, learnsets,
evolutions, encounters, map matrices, trainers, egg moves, and NPC trades, but
they are intentionally absent from the executable layout contract. Their HGSS
formats and normalization paths have not yet been verified end to end.

## Engine notes

The distinct `gen4_hgss` leaf adapter supports Pokémon, abilities, and moves.
Real HeartGold, SoulSilver, and Platinum fixtures prove that their personal,
English-message, and move-record formats share Generation IV parsers, which live
in shared generation code. HGSS does not reuse the Platinum adapter: encounter
records, map data, scripts, trainers, items, and ancillary Pokémon data remain
unsupported until independently verified. Unsupported semantic formats are
declared explicitly by the adapter.

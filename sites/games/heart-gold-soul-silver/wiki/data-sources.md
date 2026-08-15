# Data sources

## Primary ROMs

- Pokémon HeartGold (USA): header code `IPKE`, ROM version 0, SHA-256
  `65f02a56842b75aa92d775d56d657a56fe3fa993550b04dc20704ab82d760105`.
- Pokémon SoulSilver (USA): header code `IPGE`, ROM version 0, SHA-256
  `51d0f94a16af7d77c067b4cb7d821ba890a13203a2e2c76049623332c0582e20`.

## Publication model

HeartGold and SoulSilver are published as a sibling-version family. Both ROMs
are parsed independently and merged by stable record identity; shared records
appear once and version-specific records retain explicit applicability.

## Coverage and provenance

Each retail ROM produces 505 public Pokémon and battle-form records, 123 public
abilities, 467 playable moves, 513 public items, 142 wild-encounter areas, 737
trainers, and 540 packed map-header locations. The detailed location data includes
1,317 warps, 158 directional connections, 390 trainer-object links, 256 visible
items, and 240 hidden items. Internal archive records remain available in the
normalized datasets for auditing but do not receive public pages.

PokéDB supplies canonical names, links, descriptive metadata, and media fallbacks.
The ROMs remain authoritative for mechanics, relationships, and version
differences.

## Engine notes

HeartGold and SoulSilver use the `gen4_hgss` leaf adapter. Formats proven
identical to Platinum reuse shared Generation IV parsers, while HGSS retains its
own encounter, packed map-header, script, and location semantics.

The sections below describe the shared HGSS engine formats and verified extraction
boundaries used by both the retail games and Sacred Gold/Storm Silver.

--8<-- "gen4/hgss-data-sources.md"

### Retail-specific verification

The paired retail personal-data, ability-name, move, and Pickup inputs are
byte-identical. Every dataset is nevertheless extracted from both ROMs so an
unexpected version difference cannot be hidden by assuming symmetry.

Script decoding recovers six of the eight previously cataloged Silver
starter-dependent battle groups plus a seventh Passerby Boy group that the old
handwritten list omitted. Silver's first Cherrygrove battle uses trainer IDs too
small to locate unambiguously, and the Dragon's Den double battle uses a different
command shape; both remain unresolved rather than inferred.

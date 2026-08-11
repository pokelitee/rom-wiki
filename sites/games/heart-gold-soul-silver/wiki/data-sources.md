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

Level-up learnsets (`a/0/3/3`), evolutions (`a/0/3/4`), the combined egg-move
table (`a/2/2/9` member 0), and all 92 TM plus 8 HM move mappings are decoded.
The machine table is located by its verified code signature rather than a
build-specific assumed offset. The 52 regular move-tutor records come from
decompressed overlay 1 at `0x23AE0`; their packed fields provide BP costs and
tutor groups, including the free Headbutt tutor in Ilex Forest. The separate
`fielddata/wazaoshie/waza_oshie.bin` file provides 505 eight-byte compatibility
rows.

The item archive at `a/0/1/7` contains 514 records of 34 bytes. Message member
222 contains 537 item names; the executable's item-to-archive map resolves the
extra named IDs without inventing records. The public dataset exposes 513
nonzero item IDs and their ROM mechanics.

Wild archive `a/0/3/7` contains 142 retail records of 196 bytes. HGSS-specific
decoding preserves morning, day, and night walking lists; surf, Rock Smash, and
three rod tables; Hoenn/Sinnoh radio species; land and surf swarms; and night
fishing/fishing-swarm replacements. Slot weights come from the game engine's
selection routines. Both retail ROMs resolve these areas through 540 packed
24-byte ARM9 map headers and the 16-byte internal map-name table.

Trainer data (`a/0/5/5`) and parties (`a/0/5/6`) contain 738 members; member 0
is unused, so 737 trainers are published. Names, classes, class genders, flags,
items, AI settings, battle type, party species/forms, levels, held items, and
custom moves are ROM-derived. Event objects link 390 trainer IDs to map headers
through HGSS's verified `script_id - 3000 + 1` convention. Script-only and
shared/tag battle links remain unavailable because HGSS battle commands are not
yet decoded. Trainer-class payout multipliers also remain unavailable: the
Platinum locator does not occur in HGSS and no unique HGSS table reference has
been established.

The Cherrygrove-through-Dragon's Den Silver branches are published as verified
Battle Variants. Script selection was checked for all Chikorita, Cyndaquil, and
Totodile choices in both retail ROMs; every variant still references its exact
trainer record. The broader phone-rematch state machines and script-only/shared
battle locations remain unresolved and are not reconstructed from trainer names.

The event archive at `a/0/3/2` has 491 members and the matrix archive at
`a/0/4/1` has 288. Together they publish 1,317 warps, 158 directional
connections, and nine explicitly dynamic warps across 540 maps. Retail events
resolve 256 visible and 240 hidden item references. Destination bounds and
destination-warp existence are validated before publication.

The in-game trade archive at `a/1/1/2` and message member 200 publish 11 true
NPC trades. Shuckie and Kenya are excluded because their records are gift-like
static Pokémon, not exchanges. A unique ARM9 catalog signature publishes 27
supported specialty shops containing 141 item entries. Their map placement is
not claimed because the corresponding HGSS script commands remain undecoded.

Pickup uses two uniquely located tables in decompressed battle overlay 12: 18
common and 11 rare items expand into ten level bands, each with exact slot
probabilities totaling 100%. Both retail versions produce the same tables.

PokéDB supplies names, links, descriptive metadata, and media fallbacks. The ROM
remains authoritative for stats, types, held-item IDs, growth data, abilities,
and TM/HM compatibility flags.

Sacred Gold and Storm Silver inherit the same verified extraction contract.
Their patched NARCs carry exact, profile-scoped size inconsistencies, and their
wild records are 192 bytes rather than 196; the absent final night-fishing and
fishing-swarm fields remain unavailable instead of receiving placeholder values.

## Engine notes

The distinct `gen4_hgss` leaf adapter owns HGSS encounter and map-header formats.
Real HeartGold, SoulSilver, and Platinum fixtures prove that personal, messages,
moves, items, learnsets, evolutions, machines, egg moves, trainer records, and
party records genuinely share Generation IV parsers, which live in shared code.
HGSS does not reuse the Platinum adapter or its Sinnoh-specific scripts and
location semantics. Static encounters, gifts and eggs, Headbutt tree tables,
and Safari Zone block configuration remain explicit blockers: their files or
retail offsets are known, but their complete HGSS semantics and hack-safe
associations are not decoded into the normalized contracts.

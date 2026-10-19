# Data sources

## Primary ROM

- Pokémon Emerald (USA, Europe): header code `BPEE`, ROM version 0, SHA-256
  `a9dec84dfe7f62ab2220bafaef7479da0929d066ece16a6885f6226db19085af`.

## Publication model

Pokémon Emerald is published as a single-game retail reference.

## Coverage and provenance

This ROM produces 386 public Pokémon, 76 abilities, 354 playable moves, 376
items, 124 wild-encounter areas, 855 trainers, and 482 map locations. Pokémon
pages include level-up learnsets, egg moves, evolutions, TM/HM compatibility,
all 30 move tutors, and wild held items. The ROM's 25 "?" placeholder species
records remain in the normalized datasets for auditing but do not receive
public pages.

PokéDB supplies reference identity, sprites, and Pokédex text. The ROM remains
authoritative for mechanics and relationships, and the wiki always
distinguishes ROM-derived facts from reference content.

## Engine notes

Emerald uses the `gen3_emerald` leaf adapter, which shares its Generation III
record formats with FireRed and LeafGreen. GBA ROMs have no file system, so
every table is read at a profile-declared offset and validated by size and
value range rather than located by name.

- **Species identity:** the personal table holds 412 records. Internal species
  IDs follow the ROM's own internal-to-National-Dex table, and names come from
  the ROM's species-name table. Records 252–276 are unused "?" placeholders
  with identical stats and no abilities.
- **Abilities:** ability 76 (Cacophony) is unused, so the ROM's ability IDs
  from 77 onward are shifted down by one to match the reference numbering.
- **Learnsets:** level-up moves come from a pointer table of per-species lists
  of packed `level << 9 | move` entries terminated by `0xFFFF`.
- **Locations:** every map is read through the ROM's map-group table, and
  names come from the region-map section table. Maps in the dynamic section
  (used by the S.S. Tidal) have no name and are skipped.
- **Move tutors:** the tutor move table and 4-byte per-species compatibility
  masks cover 30 tutors. Ten are field NPCs; the other 20 are Battle Frontier
  tutors reached through script specials 474 and 475. Battle Point costs are
  not decoded.
- **Names:** all-caps ROM names are recased per word ("HP Up", "TM01", "Poké
  Ball"); descriptions keep their ROM text. Names that later games write with
  an inner capital read as one word, e.g. "Thunderpunch".

Battle Frontier facilities, contests, and Berry mechanics are not covered.
Trainers are published exactly as the ROM stores them, including unused
entries.

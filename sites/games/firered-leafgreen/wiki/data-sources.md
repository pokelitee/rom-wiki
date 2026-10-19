# Data sources

## Primary ROMs

- Pokémon FireRed (USA): header code `BPRE`, ROM version 0, SHA-256
  `3d0c79f1627022e18765766f6cb5ea067f6b5bf7dca115552189ad65a5c3a8ac`.
- Pokémon LeafGreen (USA): header code `BPGE`, ROM version 0, SHA-256
  `78d310d557ceebc593bd393acc52d1b19a8f023fec40bc200e6063880d8531fc`.

## Publication model

FireRed and LeafGreen are published as one paired retail reference. Both
ROMs are parsed independently and merged by stable record identity; shared
records appear once and version-specific records state which game provides
them.

## Coverage and provenance

The paired ROMs produce 386 public Pokémon, 76 abilities, 354 playable moves,
374 items, 132 wild-encounter areas, 743 trainers, and 425 map locations.
Pokémon pages include level-up learnsets, egg moves, evolutions, TM/HM
compatibility, all 15 move tutors, and wild held items. The ROMs' 25 "?"
placeholder species records remain in the normalized datasets for auditing
but do not receive public pages.

Location pages also show the map's warps (1294) and connections (116), 339
item balls and hidden items, 60 items handed over by scripts, 13 static
encounters, 7 gift Pokémon and Eggs, 23 marts, and 9 in-game trades.

PokéDB supplies reference identity, sprites, and Pokédex text. The ROMs remain
authoritative for mechanics, relationships, and version differences, and the
wiki always distinguishes ROM-derived facts from reference content.

## Engine notes

FireRed and LeafGreen use the `gen3_frlg` leaf adapter, which shares its
Generation III record formats with Emerald. GBA ROMs have no file system, so
every table is read at a profile-declared offset and validated by size and
value range rather than located by name.

- **Species identity:** the personal table holds 412 records. Internal species
  IDs follow the ROM's own internal-to-National-Dex table, and names come from
  the ROM's species-name table. Records 252–276 are unused "?" placeholders
  with identical stats and no abilities.
- **Abilities:** ability 76 (Cacophony) is unused, so the ROM's ability IDs
  from 77 onward are shifted down by one to match the reference numbering.
- **Learnsets:** level-up moves come from a pointer table of per-species lists
  of packed `level << 9 | move` entries terminated by `0xFFFF`. Deoxys has a
  different learnset in each version, and Dugtrio's level-1 moves are stored
  in a different order; both are kept as version variants.
- **Locations:** every map is read through the ROM's map-group table, and
  names come from the map-section name table, whose first entry is map
  section 88.
- **Map events and scripts:** each map's warps, connections, objects, signs,
  and triggers are read from its event tables. Its scripts are disassembled
  with the command layouts from the pret decompilations, following every
  jump and call. Location pages list item balls (`finditem`), hidden items,
  items handed over (`giveitem`/`additem`), static encounters
  (`setwildbattle` and event legendaries), gift Pokémon and Eggs, marts, and
  in-game trades. Only literal commands count; a value held in a script
  variable, such as a starter, is left out.
- **Move tutors:** the tutor move table and 2-byte per-species compatibility
  masks cover 15 tutors, each located from the script that teaches its move.
- **Names:** all-caps ROM names are recased per word ("HP Up", "TM01", "Mt.
  Moon"); descriptions keep their ROM text. Names that later games write with
  an inner capital read as one word, e.g. "Thunderpunch".

Trainers are published exactly as the ROMs store them. About 100 unused
trainer slots share one placeholder party (a level-5 Ekans) and have no name,
and the rival keeps the ROM's default name.

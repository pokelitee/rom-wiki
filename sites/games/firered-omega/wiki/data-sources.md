# Data sources

## Primary ROM

- Pokémon FireRed Omega by Drayano: header code `BPRE`, ROM version 0,
  SHA-256 `a1939737dad5b41eb4f61d2c7e5844c765b66ea8f6c3ef52b66eedc5420e4471`.
  The ROM names no release version.

## Publication model

FireRed Omega is published as a single-game hack reference. Every supported
dataset is compared with the exact USA retail Pokémon FireRed ROM (header code
`BPRE`, ROM version 0, SHA-256
`3d0c79f1627022e18765766f6cb5ea067f6b5bf7dca115552189ad65a5c3a8ac`).

## Coverage and provenance

The patched ROM produces 386 public Pokémon, 76 abilities, 354 playable moves,
374 items, 143 wild-encounter areas, 743 trainers, and 439 map locations,
including the hack's new areas such as Yggdrasill Forest and the Sanctuaries.
Location pages also show the map's warps (1339) and connections (116), 353
item balls and hidden items, 61 items handed over by scripts, 27 static
encounters, 19 gift Pokémon and Eggs, 23 marts, and 9 in-game trades. One
object's script points at unused bytes and is skipped.

Pokédex entries and move, item, and ability descriptions come from the ROM's
own text. PokéDB supplies reference identity and sprites. The ROM remains
authoritative for mechanics, and the wiki always distinguishes ROM-derived
facts from reference content.

## Engine notes

FireRed Omega uses the same `gen3_frlg` engine as retail FireRed, and its
profile extends the retail one. Every table stays at its retail address
except two, which every code reference in the hack now points to:

- the wild-encounter headers, moved to `0x72CE50` and grown from 132 to 143;
- `gMapGroups`, moved to `0x71BE34` with a 44th group of 14 new maps.

The hack leaves the original groups' map lists in place, so the ROM stores
no per-group map count. A group ends at the next group's list or at its first
entry that doesn't point to a map header.

Map events, scripts, and prize money are decoded as for retail FireRed; see
its data sources page. Omega edits the money values, including the default
for unlisted classes (30 instead of 5).
Rematch groups aren't published until Omega's own rematch table is verified.

Trainers are published exactly as the ROM stores them, including unused
slots, and the rival keeps the ROM's default name.

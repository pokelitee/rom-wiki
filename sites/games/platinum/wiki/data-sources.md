# Data sources

## Primary ROM

- Pokémon Platinum (USA): header code `CPUE`, ROM version 0, SHA-256
  `ede62292aa7f7014ff27d42097e769753380531739889c29b968b67b80f80678`.

## Publication model

Platinum is published as a single-game retail reference. This exact ROM is also
the clean comparison baseline for the Renegade Platinum wiki.

## Coverage and provenance

The wiki derives Pokémon, abilities, items, moves, the type chart, wild
encounters, trainers, and locations directly from the ROM. PokéDB supplies
reference names, descriptions, links, and sprites; it is not used as a
mechanics baseline. Explicit annotations supplement facts that are not
represented directly in table-driven ROM data, while ROM-derived values remain
authoritative for every field stored by the ROM.

## Engine notes

Platinum uses the Generation IV reference engine (`gen4_dppt`). The later
Generation V engines (`gen5_bw` and `gen5_b2w2`) follow the extraction and
provenance boundaries established here where their platform structures match.

The sections below describe the shared Generation IV DPPt-engine record
formats and decoding techniques; this page adds this specific release's own
verified facts and configuration on top.

--8<-- "gen4/dppt-data-sources.md"

## Roaming Pokémon

Roaming Pokémon are audited through the one-byte `ActivateRoamingPokemon`
slot command. This release invokes four of five possible slots: Mesprit
(slot 0, Lake Verity's disturbance event), Cresselia (slot 1, the Fullmoon
Island request), and Moltres and Zapdos (slots 3 and 4, both released by the
Eterna Team Galactic Building battle). The fifth slot (Darkrai) has no
invoking script call anywhere in this release and is reported as inactive
rather than assumed present.

Roamer level is a compiled ARM9 constant whose exact bytes were not
locatable without a symbol table or a disassembler, so level is
intentionally left unrendered rather than guessed at — a hack that
rebalances difficulty could plausibly have changed it.

## Gift Pokémon

This release configures two profile-anchored egg gifts: Togepi and Riolu.

## Item and location facts specific to this release

Item ID-to-archive-member mapping, mart inventories, decoration/seal/Battle
Frontier prices, the Game Corner prize table, and Pickup/fossil tables are
all read from this release's own item-data archive
(`itemtool/itemdata/pl_item_data.narc`) and its own unmodified ARM9 offsets —
none of this release's tables are patched or repurposed.

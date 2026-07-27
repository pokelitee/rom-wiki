# Data sources

The primary source is the exact USA retail release of Pokémon Platinum
(header code CPUE, ROM version 0), the same clean image used as Renegade
Platinum's own comparison baseline. This is this project's first supported
release and its Generation IV reference engine (`gen4_dppt`); every other
engine this project has added since (Generation V's `gen5_bw`) is checked
against the patterns established here. Structured reference data from PokéDB
and explicit annotations supplement facts that aren't represented directly in
table-driven ROM data (see PokéDB below); ROM-derived values remain
authoritative for every field the ROM's own records store.

The sections below describe the shared Generation IV DS-engine record
formats and decoding techniques; this page adds this specific release's own
verified facts and configuration on top.

--8<-- "gen4-data-sources.md"

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

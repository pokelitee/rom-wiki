# Data sources

The primary source is Renegade Platinum standard v1.3.0, a hack built on the
same Generation IV DS engine (`gen4_dppt`) as the retail USA Pokémon
Platinum release. Structured reference data from PokéDB and explicit
annotations supplement facts that aren't represented directly in
table-driven ROM data (see PokéDB below); ROM-derived values remain
authoritative for every field the ROM's own records store.

The sections below describe the shared Generation IV DS-engine record
formats and decoding techniques (identical between this hack and the retail
release, since a hack patches table contents rather than the engine's own
record layouts); this page adds Renegade Platinum's own specific facts and
deltas from the base game on top.

--8<-- "gen4-data-sources.md"

## Renegade Platinum-specific changes

Renegade Platinum repurposes Generation IV type ID 9, the base game's unused
"Unknown" type, as Fairy — the retail release has no Fairy type at all, so
this ID is decoded and displayed as Fairy only for this profile.

Item IDs are joined to their 34-byte records through the same
item-ID-to-archive-member mapping table mechanism the base game uses, but
this hack's own table is repurposed and shifted at several item slots
relative to retail Platinum's; the mapping is still discovered and validated
directly from this ROM's own ARM9 data rather than assumed, so it correctly
follows Renegade Platinum's own repurposed slots instead of retail's.

Shared static-encounter script member 401 uses explicit map-header
annotations (`static_encounter_locations`) to associate Articuno, Moltres,
Lugia, and Kyogre with the object events that invoke their script entries.

## Roaming Pokémon

Renegade Platinum does not invoke any of the five roaming slots from its
referenced field scripts — its former roaming encounters are represented
instead by the location-bound static encounters (see the shared Items
section above), not by the `ActivateRoamingPokemon` mechanism the retail
release still uses.

## Gift Pokémon

This hack configures three profile-anchored egg gifts: Togepi, Riolu, and
Manaphy (retail Platinum configures only the first two).

## Changes vs. the base game

The [Changes](changes/index.md) page compares every dataset above against
Renegade Platinum's base game, Pokémon Platinum, identified by ROM checksum
rather than assumed from its name.

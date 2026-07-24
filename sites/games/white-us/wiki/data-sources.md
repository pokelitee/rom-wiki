# Data sources

The primary source is the exact USA/Europe NDSi-Enhanced release of Pokémon White
(header code IRAO, ROM version 0). This is this project's first Generation V
release, and currently covers Pokémon species (personal) data and Abilities.

## Pokémon species data

Personal (species) records are decoded from the `a/0/1/6` archive, confirmed
byte-for-byte identical to Pokémon Black's copy of the same archive: a fixed-layout
60-byte record per member (`PersonalInfo5BW`, PKHeX.Core) covering base stats,
types, catch rate, base experience, EV yields, common/rare wild held items, gender
ratio, hatch cycles, base friendship, growth rate, egg groups, all three ability
slots (including the Hidden Ability), safari flee rate, body color, sprite flip,
and TM/HM compatibility. The archive holds 669 total members: member 0 is an unused
placeholder record (a distinct, shorter 56-byte layout in this release, zero-padded
rather than decoded), members 1-649 are the national Pokédex species, members
650-667 are 18 alternate-forme records not yet resolved to a public page, and the
final member is an unrelated 1300-byte table excluded from extraction entirely.

The wild held item's third slot (Dark Grass encounters, present in this release but
absent from Generation IV) is decoded internally but not yet surfaced in the
published dataset.

## Text and names

Pokémon, ability, move, and item display names are decoded directly from this
ROM's own text archive at `a/0/0/2`, confirmed byte-for-byte identical to Pokémon
Black's copy, rather than from PokéDB. Each name table is a member of that archive
(Pokémon names at member 70, ability names at 182, move names at 203, item names
at 54); type names have no ROM text table in this generation (Generation V added
no new types over Generation IV) and remain a built-in engine constant instead.

## Not yet available

Moves, Items, Wild Encounters, Trainers, and Locations are not built for this
release yet -- each needs its own Generation V record-layout research, and for
Trainers/Wild Encounters/Locations, this release's own script-engine opcode table,
none of which carry over from the Generation IV engine this project already
supports. Because Items isn't built, Pokémon pages link to item pages that don't
exist in this build.

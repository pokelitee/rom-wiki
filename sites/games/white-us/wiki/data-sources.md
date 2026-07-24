# Data sources

The primary source is the exact USA/Europe NDSi-Enhanced release of Pokémon White
(header code IRAO, ROM version 0). This is this project's first Generation V
release, and currently covers Pokémon species (personal) data only.

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

Pokémon, type, and ability names and descriptions come from PokéDB rather than this
ROM's own text, since Generation V message-archive decoding is not yet implemented.
The wild held item's third slot (Dark Grass encounters, present in this release but
absent from Generation IV) is decoded internally but not yet surfaced in the
published dataset.

## Not yet available

Moves, Abilities, Items, Wild Encounters, Trainers, and Locations are not built for
this release yet -- each needs its own Generation V record-layout research, and for
Trainers/Wild Encounters/Locations, this release's own script-engine opcode table,
none of which carry over from the Generation IV engine this project already
supports. Because the Abilities section isn't built, Pokémon pages link to ability
pages that don't exist in this build.

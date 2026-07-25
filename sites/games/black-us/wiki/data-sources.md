# Data sources

The primary source is the exact USA/Europe NDSi-Enhanced release of Pokémon Black
(header code IRBO, ROM version 0). This is this project's first Generation V
release, and currently covers Pokémon species (personal) data, Abilities, and
Items.

## Pokémon species data

Personal (species) records are decoded from the `a/0/1/6` archive, a fixed-layout
60-byte record per member (`PersonalInfo5BW`, PKHeX.Core): base stats, types, catch
rate, base experience, EV yields, common/rare wild held items, gender ratio, hatch
cycles, base friendship, growth rate, egg groups, all three ability slots (including
the Hidden Ability), safari flee rate, body color, sprite flip, and TM/HM
compatibility. The archive holds 669 total members: member 0 is an unused
placeholder record (a distinct, shorter 56-byte layout in this release, zero-padded
rather than decoded), members 1-649 are the national Pokédex species, members
650-667 are 18 alternate-forme/battle-transformation records (Deoxys, Wormadam,
Giratina, Shaymin, Rotom, and Basculin's independently-obtainable forms, plus
Castform, Darmanitan, and Meloetta's battle-only transformations), and the final
member is an unrelated 1300-byte table excluded from extraction entirely.

Of the 18 records, 13 are real, independently-obtainable forms and are resolved to
their real species/form identity and given a public page, same as Generation IV's
alternate formes. The remaining 5 (Castform's weather forms, Darmanitan's Zen Mode,
and Meloetta's Pirouette Forme) are battle-only transformations with no independent
existence -- they're decoded and shown on their base species' page under a
"Battle-only forms" section rather than given their own page.

The wild held item's third slot (Dark Grass encounters, present in this release but
absent from Generation IV) is decoded internally but not yet surfaced in the
published dataset.

## Items

Item records are decoded from the `a/0/2/4` archive, a fixed-layout 36-byte
record per member: item ID maps directly to archive member index (no ARM9
item-to-member mapping table exists in this generation, unlike Generation IV).
There is no public documentation or decompilation of this record format to
check against, so only fields that were cross-referenced against real ROM data
and PokéDB's known Generation V item values are decoded: price (stored as
price ÷ 10 -- a real Generation V-specific difference from Generation IV, which
stores price directly), held-effect ID, fling power, fling effect ID, and pluck
effect ID. Item pocket, field/battle-use function IDs, party-use effects (HP/PP
restoration, stat boosts, status cures), Natural Gift power and type, berries,
and fossil revival are not yet decoded -- black-box comparison against real
records produced no single consistent interpretation for these fields without
a disassembly to check against, so they're left out rather than guessed. Items
whose ROM name is the archive's own "???" placeholder sentinel are excluded as
unused slots; the rare case of two distinct real items sharing a display name
(the male- and female-color Xtransceiver) is disambiguated with the item ID in
the page URL.

## Text and names

Pokémon, ability, move, and item display names are decoded directly from this
ROM's own text archive at `a/0/0/2`, rather than from PokéDB. Each name table is a
member of that archive (Pokémon names at member 70, ability names at 182, move
names at 203, item names at 54); type names have no ROM text table in this
generation (Generation V added no new types over Generation IV) and remain a
built-in engine constant instead.

## Not yet available

Moves, Wild Encounters, Trainers, and Locations are not built for this release
yet -- each needs its own Generation V record-layout research, and for
Trainers/Wild Encounters/Locations, this release's own script-engine opcode table,
none of which carry over from the Generation IV engine this project already
supports.

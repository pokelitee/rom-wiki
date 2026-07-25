# Data sources

The primary sources are the exact USA/Europe NDSi-Enhanced releases of Pokémon
Black (header code IRBO, ROM version 0) and Pokémon White (header code IRAO,
ROM version 0). This is this project's first Generation V release, and
currently covers Pokémon species (personal) data, Abilities, Items, Moves,
Wild Encounters, and Trainers.

Black and White are published as one wiki rather than two: every section this
wiki currently covers -- personal data, item data, move data, wild encounter
data, trainer data, and the ROM text archive -- is confirmed byte-for-byte
identical between the two games. Each page notes
which version(s) a record is available in; today that is always "Black &
White" for shared content, with a handful of exclusives (e.g. Zekrom in Black,
Reshiram in White) marked accordingly. If a future section (Locations, gifts)
introduces real per-version differences, the affected pages will show both
variants instead of one shared entry.

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

Level-up learnsets are decoded from the `a/0/1/8` archive (one member per
personal-data member, a simple list of move ID/level word pairs terminated by
`0xFFFF 0xFFFF`) and evolutions from the `a/0/1/9` archive (a fixed 42-byte,
7-slot record per member, unpadded -- unlike Generation IV's equivalent, which
carries two trailing padding bytes). Generation V's evolution-method IDs match
Generation IV's own scheme with one insertion -- a new "trade-special" method
at index 7 -- shifting every later method up by one; confirmed against Tyrogue
(attack/defense-comparison evolutions), Eevee (its three Stones plus
Moss Rock/Icy Rock evolutions), and Snorunt's Dawn Stone evolution.

Egg moves are decoded from the `a/1/2/3` archive: one member per species (a
dense table, unlike Generation IV's flat ARM9-overlay list), each holding a
move count followed by that many move IDs, with no terminator or padding.
Confirmed against Bulbasaur's real 14 egg moves. A few species' own records
contain a literal duplicate move ID (Swinub's lists Mud Shot twice) -- decoded
faithfully in the raw dataset since it's genuine ROM data, and deduplicated
only where it's displayed so pages don't show the same move twice.

The TM/HM move-assignment table (which move each TM/HM number teaches) lives
in the ARM9 executable, which -- unlike Generation IV's uncompressed ARM9 --
is BLZ-compressed; this project decompresses it before locating the table via
the same byte-pattern search technique the ROM-hacking community uses
(`87038803`, found once, uniquely). The table itself isn't TM01-95 followed
by HM01-06 as its move/HM counts alone might suggest -- it's TM01-92, then
HM01-06, then TM93-95, confirmed against 6 real Black ROM values (TM01=Hone
Claws, TM92=Trick Room, HM01=Cut, HM06=Dive, TM93=Wild Charge, TM95=Snarl) and
each machine's real TM/HM item ID from the ROM's own item-name table. Move
tutors, meanwhile, aren't a gap: Generation V's original Black/White never
had them at all -- they were introduced in the Black 2/White 2 sequels.

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

## Moves

Move records are decoded from the `a/0/2/1` archive, a fixed-layout 36-byte
record per member: move ID maps directly to archive member index. The archive
holds 560 total members: member 0 is an unused placeholder record, and members
1-559 are the real moves (`moveCount = 559`,
Ajarmar/universal-pokemon-randomizer-zx). As with Items, there is no public
disassembly of this record format to check every field against, so only
fields cross-referenced against known real move data are decoded: type,
damage class (status/physical/special), power, accuracy, PP, priority,
secondary-effect chance, target, an opaque effect ID, and a battle-flags
bitmask. Generation V removed Contests entirely, so (unlike Generation IV)
there are no contest-effect or contest-type fields to decode.

## Wild encounters

Wild encounters are decoded from the `a/1/2/6` archive: 112 members, each
either one 232-byte block (no seasonal variation) or four consecutive
232-byte blocks (spring/summer/autumn/winter, in that order), completely
unlike Generation IV's `pl_enc_data.narc` shape. Each block holds a 7-byte
rate header -- one byte per encounter method -- followed by that method's
slot table: 12 slots each for Grass/Cave, Doubles Grass, and Shaking Spots
(Generation V's name for the "Dark Grass" rustling-grass mechanic, whose
possibility is already decoded as part of each Pokémon's own wild-held-item
data), and 5 slots each for Surfing, Surfing Spots, Fishing, and Fishing
Spots. Each slot is a word (an 11-bit species ID plus a 5-bit forme index --
confirmed against a Basculin fishing slot resolving its color-stripe forme
correctly) followed by minimum/maximum level bytes. Confirmed against real
Black ROM data across several areas: real, level-appropriate species for
early routes (Patrat, Lillipup, Purrloin) and mid-game water routes
(Palpitoad, Shelmet, Stunfisk, Seismitoad, Barboach, Whiscash). Slot chance
percentages aren't stored in the ROM -- like every other generation since
Generation III, they're a fixed engine weighting applied by slot position.

Real in-game location names aren't attached to encounter areas yet, for a
narrow, specific reason: the map-name lookup table itself (`a/0/1/2`, a
simple fixed 48-byte record per map) decodes fine, but the map name *text*
table hits a character code this project's message decoder doesn't handle
yet -- an unrelated text-decoding gap, not missing ROM research on the
encounter side. Each page instead shows its ROM archive member index (and
season, if seasonal).

## Trainers

Trainer data is decoded from the `a/0/9/2` archive (20-byte fixed record per
member) and party data from `a/0/9/3` (variable-size per trainer, driven by
the trainer's own flags). The trainer record holds: flags (custom moves/held
items), class ID, battle mode (0=single, 1=double, 2=triple, 3=rotation --
this generation adds Triple and Rotation battles, unlike Generation IV's
single/double-only format), party size, four AI battle items, AI flags, a
"healer" flag, a victory-money multiplier, and a victory item. Each party
member is 8 bytes (difficulty, a byte combining ability slot and a
forced-gender flag, level, species, and forme -- all full words, unlike
Generation IV's packed species/form value), plus an optional 2-byte held item
and/or 8-byte custom-move block depending on the trainer's flags. Confirmed
against several real Black ROM trainers: Lass Jimmy's level-7 Purrloin; Gym
Leader Burgh's Emolga pair, one forced male and one forced female (confirming
the gender-flag bit meaning); and a real level-75-77 rematch team (three
elemental monkeys, Liepard, Swoobat, and Zebstrika) with real held items and
move sets, whose party data ends exactly on the computed record boundary
with zero leftover bytes.

Ability slot 0 and an unforced gender are genuine in-game randomness for this
generation, not something recorded in the ROM (Generation IV's trainers, by
contrast, use a documented, reproducible personality-value algorithm this
project already replicates for that generation) -- so unlike a stored
ability slot or a forced gender, they're left unavailable rather than
guessed. The same applies to nature and calculated stats: Generation V
trainer parties have no stored nature field and no publicly documented,
reproducible derivation for one, so both stay unavailable.

Real map locations and script references aren't attached to trainers yet:
that needs this generation's own script-engine opcode table (to find each
trainer's field battle trigger), which hasn't been researched. This is the
same underlying gap that blocks Locations and static (gift/single) Pokémon
encounters below -- unlike wild encounters' location-linking gap, which is
narrowly a text-decoder issue, this one is genuinely unresearched.

## Text and names

Pokémon, ability, move, and item display names are decoded directly from each
ROM's own text archive at `a/0/0/2`, rather than from PokéDB. Each name table is a
member of that archive (Pokémon names at member 70, ability names at 182, move
names at 203, item names at 54); type names have no ROM text table in this
generation (Generation V added no new types over Generation IV) and remain a
built-in engine constant instead.

## Not yet available

Locations are not built for this release yet -- it needs its own Generation V
record-layout research, and this release's own script-engine opcode table
(shared with Trainers' location-linking gap above), none of which carry over
from the Generation IV engine this project already supports. Static
(gift/single) Pokémon encounters are part of this same gap, since they're
script-driven rather than part of the wild encounter table already decoded.

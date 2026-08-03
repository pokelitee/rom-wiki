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
absent from Generation IV) is decoded from a word at offset 0x10 and shown as a
third "Dark Grass" row alongside the common/rare held items. Confirmed against a
specific, well-documented real fact: Sawk holds Black Belt normally but a
distinct Expert Belt in Dark Grass.

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

Static (gift/single-Pokémon) encounters -- starter-choice monkeys, event
legendaries, fossil revivals, and similar -- are decoded from 31 literal
`[script-file, byte-offset]` facts published by
Ajarmar/universal-pokemon-randomizer-zx's own tooling, read directly out of
the `Scripts` archive (`a/0/5/7`). Each fact is a
plain species ID (and, unless it's a gift egg, a level byte) patched into one
specific script file, the same "adopt-and-verify a literal fact" pattern as
NPC trades and specialty shops. Verified against 12 real Black ROM facts:
starter-choice monkeys (level 10), the free tutorial Magikarp (level 5), the
Dreamyard Munna/Zorua events, the Larvesta gift egg, the post-game legendary
trio and Landorus/Kyurem, Reshiram/Zekrom, and two fossil revivals -- all
real, correct, level-appropriate facts. Each affected Pokémon's page shows a
"Static encounters" section listing its level (or "Egg"). The location
pipeline also matches each dedicated script file to its map header, so the
resolved encounters appear on their location pages with location links on the
Pokémon pages. The shared fossil-revival script is the one exception because
it is invoked by a map script rather than assigned directly to a map header;
its item-to-species facts remain visible without a guessed location.
Roaming Pokémon (Thundurus/Tornadus) were investigated the same way and found
to be a genuine exception: the *unmodified* retail ROM stores an ARM
instruction, not a data word, at the species offset the same tooling
publishes for at least one of the two (confirmed against the real Black
ROM) -- the real species is only a literal fact once a randomizer's own code
patch has been applied to the ROM, so this one case is left undecoded rather
than guessed at.

## Items

Item records are decoded from the `a/0/2/4` archive, a fixed-layout 36-byte
record per member: item ID maps directly to archive member index (no ARM9
item-to-member mapping table exists in this generation, unlike Generation IV).
There is no public documentation or decompilation of this record format to
check against, so every field below was cross-referenced against real ROM
data, PokéDB's known Generation V item values, and (for pocket assignment)
Bulbapedia's own real item-by-pocket listing: price (stored as price ÷ 10 --
a real Generation V-specific difference from Generation IV, which stores
price directly), held-effect ID, fling power, fling effect ID, pluck effect
ID, bag pocket (this generation has only 5 pockets, down from Generation
IV's 8 -- Poké Balls, Battle Items, and Mail were folded into a single
general "Items" pocket), field-use function ID (byte-identical to Generation
IV's own enumeration, plus one new entry for the Dowsing MCHN -- this
generation's Itemfinder replacement, with no Generation IV counterpart),
battle-use function ID (a raw ID, not exhaustively named), whether an item
can be discarded (`prevent_toss`) and registered to the touch-screen
quick-select button (`selectable`), and a battle-bag category bitmask
(`battle_pocket_mask`) -- all three at the exact same bit positions
Generation IV's own item record already uses, verified against the real
Black ROM's full item table: `prevent_toss` is true for exactly the 120
real non-discardable items (every TM/HM, every real key item); `selectable`
is true for exactly the 7 real quick-select-registerable items (Town Map,
Bicycle, Super Rod, Vs. Recorder, Dowsing MCHN, Pal Pad, Gracidea);
`battle_pocket_mask` forms a coherent category bitmask (Poké Balls, HP
medicine, and status medicine each get their own bit, and Full Restore --
the one item that does both -- is the only item with both bits set).
Generation IV's own `hold_effect_parameter` byte was re-checked and
confirmed to genuinely not carry one coherent fact in this generation: it
tracks the HP/PP restore amount for every healing item regardless of
whether that item's own held-item effect ID is even set, which isn't what
a real hold-effect parameter should do, so it stays undecoded. Natural Gift
power and type (verified against Oran Berry, Sitrus Berry, and Micle Berry's
well-documented real types and powers), and party-use effects -- HP/PP
restoration amounts, six independent per-stat EV change amounts (verified
against all 6 EV vitamins and all 6 EV-reducing berries, 12 independent real
facts), status-cure bitmask, friendship-change amounts, and a small
disambiguated revive/whole-party-revive/level-up flag (an initial "bit 0
means revive" reading turned out to have a false positive on Rare Candy;
checking it against the ROM's *entire* item table rather than a handful of
samples caught the collision and led to the real 3-bit encoding). Several
Generation IV item-effect concepts (Guard Spec.'s stat-drop immunity,
evolution stones, infatuation cures, PP Up/PP Max) have no confirmed
Generation V bit at all and are left undecoded rather than guessed at --
this generation may simply hardcode those effects by item ID instead of
storing them as data. Berry growth (soil-planting) data doesn't exist to
decode in the first place: Generation V removed that mechanic from the base
game entirely (berries only come from wild berry trees, NPCs, and the Dream
World). Berry firmness/size/smoothness -- the properties Generation IV
stores in its own separate `nuts_data.narc` archive -- don't exist to
decode either, and this was checked directly rather than assumed: this
generation has no equivalent archive, no item-record byte matches the real
firmness groupings, and (most conclusively) the ROM's own real item
description text for every one of the 66 real berries never mentions Size
or Firmness at all, describing only gameplay effect. This matches the
mechanics that would need this data -- soil-growing and Pokéblocks/Poffins
-- being equally absent from this generation. Fossil revival is now fully decoded, including the item-to-species
mapping: every real fossil item's own field-use function ID is 0 ("none";
reviving a fossil is a specific NPC interaction, not a bag-menu action), so
the choice is hardcoded in the fossil scientist's own script logic rather
than a data table this project's item-record decode alone can reach --
unlike the opcode-signature scans that resolved trainer battles/warps/static
encounters, this needed reading the script's actual conditional-branch
logic (a chain of item-ID comparisons feeding a species variable). Verified
identically against both real ROMs: items 105/104/101/102/103/100/99/572/573
(Skull/Armor/Helix/Dome/Old Amber/Claw/Root/Cover/Plume Fossil) resolve to
species 408/410/138/140/142/347/345/564/566 (Cranidos/Shieldon/Omanyte/
Kabuto/Aerodactyl/Anorith/Lileep/Tirtouga/Archen) -- the real, well-known
pairing, now a literal decoded fact. Items whose ROM
name is the archive's own "???" placeholder sentinel are excluded as unused
slots; the rare case of two distinct real items sharing a display name (the
male- and female-color Xtransceiver) is disambiguated with the item ID in
the page URL.

The Pickup ability's held-item table is decoded from a 29-word array found by
byte-pattern search in the Battle overlay (overlay 92) -- the same technique
used for the TM/HM move table above, since this table also has no stable
absolute offset across ROM builds. Unlike Generation IV's Pickup (separate
flat common/rare item lists plus a rate curve), this generation packs every
10-level range's items into one shared array with a sliding window (a
9-item "common" window and a 2-item "rare" window, each shifting by one
entry per level range) -- a real, verified fact
(`Gen5RomHandler.getPickupItems()`'s own hardcoded formula), not a guess.
The per-slot percentages (30%, six at 10%, two at 4%, two at 1%) aren't ROM
data -- they're the same fixed engine constant Generation IV's own Pickup
uses. Verified against both real ROMs: both decode to the identical,
well-documented real Gen5 Pickup table (Potion/Antidote/Super Potion/.../Max
Elixir in the common pool; Nugget/King's Rock/Iron Ball/Prism Scale/
Leftovers in the rare tier).

NPC (in-game) trades are decoded from the `a/1/6/5` archive (108-byte fixed
records) and shown on the traded-for item's page (the same "Gifts and
trades" table Generation IV's locations use, since the underlying concept is
the same even though Generation V's trades aren't linked to a map header).
Unlike most of the gaps above, this one wasn't blocked on a missing
disassembly -- the record layout is fully documented by the ROM-hacking
community's own tooling and needs no script-engine work for the trade data
itself (only for the field location it triggers at, which isn't attempted).
Verified against 5 real, active Black ROM trades: "Lillil" the Petilil for a
Cottonee, "Redeye" the red-striped Basculin for a Minccino, "Minipete" the
Emolga for a Boldore, "Gorge" the Munchlax for a Cinccino (holding
Leftovers), and "Eeks" the Rotom for a Ditto -- species, held item, OT name,
and nickname all match the real trade NPCs exactly. Each version's
counterpart trade (e.g. White's Cottonee-for-Petilil trade) has its own
record in the same archive, correctly excluded via the ROM's own
inactive-trade index list rather than published as if live.

Along the way, an undocumented field at record offset 8 was found and
decoded: the ROM-hacking community's own tooling never reads it, but it's
the *only* byte that differs between Black's active red-striped-Basculin
trade and its otherwise-identical inactive blue-striped counterpart (0 vs
1) -- a forme ID, used to correctly link each version's Basculin trade to
its own distinct color-striped page rather than always the base form.
When paired versions attach different trades to the same item, the merged
item page and catalog include both version-specific records rather than
silently displaying only the primary version.

Persistent specialty and TM shop inventories (Herb Salesman, Incense
Salesman, vitamin shops, city Mail counters, and similar) are decoded from a
fixed word array per shop in ARM9 overlay 21 -- itself BLZ-compressed, unlike
Generation IV's overlays, and decompressed the same way Generation V's ARM9
itself was. The ROM-hacking community's own tooling documents the exact byte
offsets and sizes for every location-specific shop in this ROM revision.
Verified against the real Black ROM, the Driftveil Herb Salesman decodes to
Heal Powder/EnergyPowder/Energy Root/Revival Herb, the Driftveil Incense
Salesman to the real Incense lineup, and the TM counters to their actual TM
item IDs.

The location pipeline separately decodes each map script's call to the global
shop dispatcher. Selectors `0` through `19` link those persistent inventories
to their map pages, while selector `255` marks a standard Poké Mart whose
stock changes with badge progression. Item pages consequently link shop stock
back to map locations instead of relying only on internal shop names. Black
City and Gear Station selectors `247` through `254` use separate vendor and
currency logic; they are counted explicitly as unsupported rather than being
assigned guessed stock.

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

Real in-game location names are attached via the map header table
(`a/0/1/2`, a simple fixed 48-byte record per map): each header's own
wild-encounter-table index cross-references the encounter area it belongs
to, and its display-name index resolves through the ROM's own map-name text
table. Multiple map headers can share one encounter table (giving an area
more than one real name, e.g. several sub-areas of the same city); confirmed
against real Black ROM data (e.g. area 3 correctly resolves to "Icirrus
City"). Decoding that map-name text table required fixing a real bug in this
project's message decoder first -- see Text and names below.

These relationships are published in both directions. Each location page links
the encounter variant used by that map header, including the applicable season
and game version, while each encounter page links back to every matching map
header. Distinct headers remain distinct even when they share the same display
name, and unresolved encounter tables remain visible without invented links.

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

Real map locations and script references are now attached to trainers, closing
what used to be this section's one remaining gap. Two literal-fact
mechanisms, both cross-verified against real Black ROM data, resolve every
trainer battle trigger without a full script-engine disassembly:

- **Sight-triggered battles**: each map's overworld NPC placements
  (`a/1/2/5`, one member per map header) carry the trainer ID directly on
  the NPC record's own `scriptUsed` field, encoded as `band + trainer_id`
  where `band` is a multiple of 1000 (2000/3000/5000/7000 all seen in the
  real ROM). Confirmed against 18 real trainer records this way: two
  consecutive runs of `scriptUsed` values (3026-3034 and 7040-7048)
  resolved to trainer IDs 26-34 and 40-48, all real, sensible trainer
  records with ascending party sizes.
- **Talk-triggered/scripted battles**: each map header's own dedicated
  script file (an undecoded field at byte offset 6 of the 48-byte map
  header record, until this pass) is scanned for literal
  `CallTrainerBattle`/`CallTrainerMultiBattle` commands, the same
  "opcode signature + validating follow-on command" technique this
  project's Generation IV engine already uses for Platinum's
  `StartTrainerBattle`. The opcode table itself (`CallTrainerBattle` =
  `0x0085`, followed in every real occurrence by `TrainerBattleIsVictory` =
  `0x008D`) is adopted from FrostFalcon/FrostsGen5Editor, an actively
  maintained community Gen V ROM editor, and independently cross-checked
  against real ROM bytes (walking a known static-encounter script from its
  own function-table start lands byte-exact on the already-verified
  Magikarp species fact).

Both mechanisms resolve trainer IDs to real trainer records only -- battles
whose ID doesn't resolve are left unlinked rather than guessed at. Verified
end-to-end: trainer 13 (Cilan, Striaton City's Grass-type Gym Leader) shows
both a scripted battle at Striaton City (his tutorial fight) and a
sight-triggered appearance later at Dragonspiral Tower, matching the real
game's story.

## Locations

The map header table (`a/0/1/2`, a single-member NARC holding one fixed
48-byte record per map -- 427 total) started as a deliberate bare minimum
(just a display-name index and a wild-encounter-table cross-reference, the
only two fields the ROM-hacking community's own tooling,
Ajarmar/universal-pokemon-randomizer-zx, reads from this record) and has
since grown considerably as the rest of this section documents: real
trainers, warps, outdoor connections, field items, and static encounters
are all attached to each map page now too. Confirmed against real Black ROM
data: header 6 resolves to "Striaton City" with a wild encounter
cross-reference to table index 0; every one of the 427 headers has a valid
name index, and exactly 112 distinct wild-encounter cross-references are
used, matching the Wild Encounters archive's own 112 members exactly.

Each location page links to every rendered Wild Encounters variant selected by
its table index. A single index can expand into up to 4 seasonal encounter areas
(see Wild Encounters above), so the shared relationship index preserves each
variant's stable route key and version applicability. Encounter pages use the
same relationship index in reverse to link back to every matching map header;
an unresolved relationship remains unlinked rather than being guessed from a
display name.

Trainer cross-references are now attached to each location (see Trainers
above for the mechanism): every map page lists its real trainers, both
sight-triggered NPCs and scripted/talk-triggered ones, sourced directly from
the trainer dataset's own resolved locations.

Warps are now attached to each location too, decoded from the same
`OverworldObjectsNARC`-shaped record (`FrostFalcon/FrostsGen5Editor`'s
layout) as the NPC placements above. Verified against every real warp in the
game: checking whether each warp's destination map has its own matching
return warp (a reciprocity check, not just a one-sided reading) succeeds for
858 of 873 real warps; the remaining 15 are genuine one-way warps (holes,
ledges, cave slides), not a decoding error. A small number of warps
(6 across the whole ROM, all in "Gear Station," the Union Room's real-world
entrance) have a destination that isn't a literal map at all (the ROM's own
null-destination sentinel) -- these are shown as a "dynamic destination"
rather than guessed at, the same concept Generation IV's own Locations
section already uses for its own Union Room warps.

Field items (Item Balls and hidden items found via the Dowsing MCHN) are now
decoded too. Visible items are overworld NPCs using one specific, shared
sprite ID (the item-ball graphic) whose own `scriptUsed` field is a flat
`7000 + item_id` offset -- verified against the real ROM: that sprite is by
far the most common NPC sprite in the game, and every one of its
`scriptUsed - 7000` values resolves to a real, coherent pickup item, never
a garbage slot. Hidden items work the same way through a different section
of the same overworld-objects record ("furniture" entries) with a
`scriptUsed >= 8000` band, resolving to real, well-known real Black/White
hidden items (Odd Keystone, the four Drives, Adamant Orb, fossils scattered
near Desert Resort/Relic Castle). Furniture's own `x` coordinate turned out
to need one extra step: unlike every other overworld record's plain
integers, it's stored in 16.16 fixed point, caught by comparing a hidden
item's huge raw `x` value against its own map's NPCs' coordinates (dividing
by 65536 landed in the exact same magnitude range, across five unrelated
real maps).

Static (gift/single) Pokémon encounters are now cross-referenced to their
real map location too, reusing the same map-header-to-script-file lookup
warps and trainer battles use: each encounter's already-known
`[script-file, byte-offset]` fact is matched against the map header whose
own dedicated script file is that same file. Verified against 18 of 19 real
static encounters -- every one resolves to its real, well-known location
with zero mismatches (Volcarona → Relic Castle, Victini → Liberty Garden,
Reshiram/Zekrom → Dragonspiral Tower, and so on). The one exception (the
shared fossil-revival script) doesn't resolve because that script is a
secondary/common script invoked from the museum's own primary script, not a
map's own dedicated one -- a real, understood limitation, not a bug.

Outdoor connections are now decoded too: each map header's `matrix` field
(byte offset 4 of the 48-byte record) indexes into a separate `MapMatrix`
archive (`layout.map_matrices`) -- the same underlying design this
project's own Generation IV support already uses (`layout.map_matrices`),
just a different binary shape here (a type byte, width/height, a grid of
terrain-file references, and, for outdoor regions, a second parallel grid
of the real header ID occupying each cell). Adjacent grid cells are real,
geographically adjacent maps. Verified against real Black ROM data: the
matrix's own declared cell count matches its raw byte length exactly, and
decoding its header-ID grid places Route 1, Route 2, and Nuvema Town in
real, contiguous, correctly-adjacent positions -- Route 1's real connections
resolve to Nuvema Town, Accumula Town, Route 17, and P2 Laboratory, exactly
the real, canonical early-game path.

Location-linked shops are decoded through their actual field-script
dispatcher. Each local shop function writes a selector to work variable
`0x8000`, writes its mode to `0x8001`, then calls global script `10110`.
Selectors `0` through `19` map to the persistent specialty and TM inventory
tables in overlay 21; selector `255` identifies the standard Poké Mart whose
stock changes with badge progression. The same dispatcher shape and selector
mapping were verified in Black, White, Blaze Black, and Volt White.

Selectors `247` through `254` are retained as an explicit unsupported count
in the raw location dataset. They belong to Black City and Gear Station
vendors whose inventory/currency mechanism is separate from the overlay-21
Poké Mart catalog, so no stock is guessed for them.

## Text and names

Pokémon, ability, move, and item display names are decoded directly from each
ROM's own text archive at `a/0/0/2`, rather than from PokéDB. Each name table is a
member of that archive (Pokémon names at member 70, ability names at 182, move
names at 203, item names at 54, map names at 89); type names have no ROM text
table in this generation (Generation V added no new types over Generation IV)
and remain a built-in engine constant instead.

One control code needed extra handling: some messages contain
runtime-substituted text (e.g. "[RIVAL]'s House") marked by 0xF000 followed
by a variable ID and a count of parameter words -- not literal characters.
The decoder recognizes this and renders a `{VAR:ID}` placeholder rather than
crashing or misreading the parameter words as garbage text; the actual
runtime-substituted value isn't reproduced, since that requires knowing what
each variable ID means (undocumented, and this project's tables so far only
ever hit this in one *unused* map-name table entry, not a real page name).

## Known coverage limitations

- **Roaming Pokémon:** Thundurus and Tornadus are not decoded. The unmodified
  retail ROM stores executable code, not a data word, at the published species
  offset for at least one of them, so the species is not treated as a literal
  fact without a randomizer-style ASM patch.
- **NPC trade locations:** trade records, species, forms, held items, trainers,
  and nicknames are decoded from the detached trade archive, but their field
  scripts are not yet mapped back to location headers.
- **Black City and Gear Station vendors:** shop selectors `247` through `254`
  use vendor and currency systems outside the ordinary Poké Mart catalog. The
  extraction reports these selectors as unsupported and does not guess stock.
- **Fossil-revival location:** the item-to-species mapping is decoded, but the
  shared revival script is secondary to the museum's map script and therefore
  cannot yet be assigned to a location by the dedicated-script cross-reference.

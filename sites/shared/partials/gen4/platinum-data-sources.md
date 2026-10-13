## Pokémon species data

Personal (species) records are decoded from `poketool/personal/pl_personal.narc`,
a fixed 44-byte record per member. The archive holds 508 members
(`PERSONAL_RECORD_COUNT`): member 0 is an unused "none" placeholder, members
1-493 are the national Pokédex species (`GEN4_BASE_SPECIES_COUNT`), member 494
is an internal "egg" record, member 495 is an internal "bad egg" record, and
members 496-507 are 12 alternate-forme records (Deoxys's three alternate
formes, Wormadam's Sandy/Trash cloaks, Giratina's Origin Forme, Shaymin's Sky
Forme, and Rotom's four appliance forms), each resolved to its real
species/form identity and given its own page rather than treated as a
separate species.

Each record holds: base stats, type IDs, catch rate, base experience, a
per-stat EV-yield bitmask (2 bits each for HP/Attack/Defense/Speed/Special
Attack/Special Defense), common and rare wild held items, gender ratio, hatch
cycles, base friendship, growth rate, egg groups, both ability slots (this
generation predates the Hidden Ability slot Generation V adds), safari flee
rate, body color and sprite-flip flag (packed into one byte), and a 128-bit
TM/HM compatibility mask covering every machine ID from 1 to 128.

Level-up learnsets are decoded from `poketool/personal/wotbl.narc`: one member
per personal-data member, a variable-length list of packed 16-bit entries
(level in the high 7 bits, move ID in the low 9 bits) terminated by `0xFFFF`,
with an optional trailing zero pad byte. Evolutions come from
`poketool/personal/evo.narc`, a fixed 44-byte, 7-slot record per member (method
ID, parameter, and target species ID per slot, 6 bytes each) with two trailing
padding bytes that must be zero; slots are contiguous, so an empty slot always
marks the end of a species' real evolution methods.

Egg moves are decoded from a flat, dense table in ARM9 overlay 5 (not a NARC
archive, unlike Generation V's per-species `a/1/2/3` layout) at a fixed
offset: a single stream of packed 16-bit words where species boundaries are
marked by a value in the `20001`-`20493` range (`20000 + species_id`) rather
than by a fixed-size per-species block, terminated by `0xFFFF`. Species
markers must appear in strictly increasing order and move IDs must fall in
the valid `1`-`467` range, both enforced as validation rather than assumed.

## Items

Item records are decoded from a fixed-layout 34-byte record per member.
Item ID does not map directly to its archive member: a separate 8-byte-record
ARM9 table supplies the real item-ID-to-member mapping, located by
fingerprinting its own first 64 entries (which are always the identity
mapping) and then validated as a true bijection onto every archive member
before being trusted.

Each record holds: price, hold-effect ID and its associated parameter byte,
pluck-effect ID, fling effect ID and power, Natural Gift power and type,
a flags word (Natural Gift type, `prevent_toss`, `selectable`, field pocket
ID, and a battle-pocket category bitmask — the same bit layout Generation V's
own item records reuse), field-use and battle-use function IDs, a party-use
flag, a 56-bit party-effect bitfield (healing, EV changes, status cures,
friendship changes, and stat-stage flags), six signed per-stat EV-change
amounts, HP/PP restore amounts, and three signed friendship-change amounts
for low/mid/high current-friendship bands.

Common Poké Mart stock and badge requirements come from a shared ARM9
progression table; specialty inventories (Veilstone's decoration counter,
Sunyshore's weekday seal shop, and the Battle Frontier's BP exchange) come
from a separate ARM9 inventory-pointer table selected by each clerk's own
field-script command, with prices read from their own dedicated ARM9 tables
(a 28-byte decoration-goods table, a 10-byte seal-price table, and a 41-entry
Battle Frontier BP-price table in ARM9 overlay 7) rather than the main
item-price field, since none of the three are ordinary money-priced items.
The Game Corner's Prize Exchange counter (Veilstone, header 144) reads its
own fixed 19-entry {item, price} ARM9 table the same way, verified
byte-for-byte against the decompilation.

Direct Pokémon gifts are decoded from literal `GivePokemon` field commands,
including their level and held item; a handful of egg gifts come from
profile-anchored `[script-file, byte-offset]` facts instead, since `GiveEgg`'s
own opcode has no reliable adjacent signature to distinguish a real command
from an unrelated operand the way `GivePokemon`'s does. Conditional script
branches can make some listed gift outcomes mutually exclusive rather than
all simultaneously obtainable in one playthrough. See this game's own notes
below for exactly which egg gifts it configures.

Static (gift/single) Pokémon encounters are decoded from literal
`WildBattle`, `LegendaryBattle`, `FatefulEncounter`, and
`GiratinaOriginBattle` field commands, each validated by a following
battle-result check (`CheckWonBattle`, or for the latter two, a `ClearFlag`
then `CheckWonBattle`). The latter two commands preserve the
encounter-specific setup used at Flower Paradise and in the Distortion World.
Some static encounters have their map location recorded as explicit profile
metadata (`static_encounter_locations`) rather than resolved automatically,
since their script member is shared/common rather than a dedicated map
script; commands whose species or level comes from a script variable instead
of a literal value are excluded until their control flow can be resolved
exactly rather than guessed at.

In-game trades are joined from literal `InitNPCTrade`/`StartNPCTrade` field
command sequences and four fixed 80-byte records in
`fielddata/pokemon_trade/fld_trade.narc`. Each record supplies the requested
and offered species, six fixed IVs (reordered from the ROM's own raw field
order to HP/Attack/Defense/Special Attack/Special Defense/Speed), Cool,
Beauty, Cute, Smart, and Tough contest stat values, a personality value whose
value modulo 25 selects one of the 25 standard natures, held item, OT
ID/gender/language, and a requested-species check. Two remaining record
fields are confirmed genuinely unused rather than merely undecoded, matched
field-for-field against pret/pokeplatinum's public decompilation of the same
struct. Nicknames and OT names come from message member 370, one nickname
and one OT name per trade in the same fixed order as the records; the
received Pokémon inherits the level of the Pokémon traded away rather than a
stored level.

Pickup and Honey Gather's held-item tables come from four fixed arrays in
ARM9 overlay 16 (18 common-tier entries, 11 rare-tier entries, and their own
9- and 10-entry per-level-range rate curves) — a different, unpacked shape
from Generation V's single sliding-window array, since this generation gives
each ability its own independent common/rare list rather than sharing one
array between them. Fossil revival (which Pokémon reviving each of the seven
fossil items produces) comes from its own fixed 7-entry ARM9 table.

## Moves

Move records are decoded from a fixed-layout 16-byte record per member; move
ID maps directly to archive member index. The archive holds 471 members
(`MOVE_RECORD_COUNT`), with real move IDs running from 1 to 467
(`MAX_MOVE_ID`). Each record holds: an opaque effect ID, damage class
(physical/special/status), power, type, accuracy, PP, secondary-effect
chance, target, a signed priority value, a battle-flags byte, and (unlike
Generation V, which removed Contests) a contest-effect ID and contest-type
ID.

## Wild encounters

Wild encounters are decoded from `fielddata/encountdata/pl_enc_data.narc`,
one record per area in one of two fixed sizes (380 or 424 bytes; the larger
variant adds a Super Rod table absent from the smaller one). Each record
holds a walking-grass table (a rate word followed by 12 level/species pairs)
and four fishing-rod tables (Old Rod, Good Rod, Super Rod where present, and
Surf), each a rate word followed by 5 slots of (max level byte, min level
byte, species ID word). Slot-chance percentages aren't stored in the ROM —
like every generation since Generation III, they're a fixed engine weighting
applied by slot position (e.g. walking: 20/20/10/10/10/10/5/5/4/4/1/1).

Several special-encounter categories overwrite specific walking-slot indices
rather than being separate tables: swarms overwrite slots 0-1, time-of-day
(day/night) replacements overwrite slots 2-3, and dual-slot substitutions (5
Game Boy Advance titles, each with its own species pair) overwrite slots 8-9.
A separate 4-species Poké Radar table exists per area but is generally not
applied, since most real Radar encounters instead continue the current
chain's species through a separate in-game routine this project doesn't
model. Unown's per-area letter set is resolved from the record's own table
ID against 8 grouped 28-letter tables taken directly from the game's own
decompiled source; a table ID of 0 means the area has no Unown encounters.

Real in-game location names are attached via the map header table (see
Locations below): each area's own encounter-table cross-reference and
display-name index resolve through the same header records the Locations
and Trainers sections use.

## Trainers

Trainer data is decoded from `poketool/trainer/trdata.narc` (20-byte fixed
record per member) and party data from `poketool/trainer/trpoke.narc`
(variable-size per trainer, driven by the trainer's own flags). The trainer
record holds: flags (custom moves/held items), class ID, party size, four AI
battle items, AI flags, and a battle type (single/double; this generation has
no Triple or Rotation format, both introduced in Generation V). Each party
member is a packed 6-byte base record (difficulty, a byte combining ability
slot and forced-gender flag, level, and a packed species/form word) plus an
optional 2-byte held item and/or 8-byte custom-move block depending on the
trainer's own flags, and a trailing 2-byte "ball seal" field always present
regardless of flags.

When that custom-move block is absent, the generated party page derives the
four most recent distinct moves available from that ROM's own level-up learnset
at the party member's level. Those moves are explicitly labeled as derived;
they are not represented as bytes stored in the trainer-party record.

Trainer class gender is read from a dedicated one-byte-per-class ARM9 table:
a value of 1 means the class is female, values 0 and 2 both mean male (2
being a mixed/double-battle-class value with no independent gender meaning
of its own).

Real map locations and script triggers are resolved two ways: overworld
object events carry the trainer ID directly in a fixed script-ID range
(3000-3999, with a documented +1 offset between script ID and trainer ID),
and scripted/talk-triggered battles are found by scanning each map's own
script file for a literal `StartTrainerBattle` command whose operands are
valid trainer IDs and whose follow-on command (6 bytes later) is any real
script opcode — deliberately not a check for `CheckWonBattle` specifically,
since requiring that exact opcode silently dropped whole battle categories
that handle their own result differently (on Platinum, the Elite Four's
battles are followed by `0x001B` and the rival battles by `0x0016`); the
operand constraints, not a specific follow-on, are what keep the scan
selective. This is the same
"opcode-signature-plus-validating-follow-on-command" pattern this project's
Generation V engine later adopted for its own equivalent trainer-battle scan.

Starter-variable branches for the rival's battles are decoded from each
profile's own scripts rather than listed by hand. One opcode is named — the
command that reads the player's starter species into a script variable. From
there the engine finds each comparison against that variable, follows the
conditional jump that guards it, and reports the exact trainer record the branch
lands on; the record no branch jumps to is the remaining starter's. A group is
only published when at least two branches each resolve onto a literal battle
command, so a script that merely contains many battles yields nothing instead of
a guess, and the species names come from the profile's own name table.

Because nothing is hardcoded, a hack that renumbers, relocates, or re-teams
these battles is described from its own ROM. Renegade Platinum uses an explicit
v1.3.0 profile contract and resolves to the same five groups with the same
species-to-record mapping as retail. Battle sites are likewise the maps the
profile's scripts place the records on, which corrected two descriptions carried
over from hand-written labels: the first rival battle is on Route 203 rather
than Route 201, and the post-Hearthome battle is on Route 209 rather than in
Hearthome City. Other same-name records remain fallback navigation only.

Where a starter branch jumps to the start of a block rather than onto a battle,
as the Survival Area pair does, the block's staged battles are paired by
position across the branches. That is only attempted once the game's own starter
accessor has been decoded, because the starter variable doubles as the engine's
general-purpose scratch variable: without knowing which species are really
starters, an unrelated comparison captures a battle belonging to the
fall-through and publishes a confident but wrong branch. Direct branch targets
are still preferred wherever they resolve, since they stay stable across hacks
that pack extra battles into the same script. The fall-through block is located
either side of the branched region, because Renegade Platinum emits it last
where retail emits it first.

The Spear Pillar partner battle, the weekend rematch stages, the starter
demonstration, and the Pokémon League rival rematch have no literal battle
command anywhere in the scripts, so there is nothing to resolve and they are
left unresolved rather than asserted. Renegade Platinum publishes one fewer
Survival Area group than retail because it empties those trainer records
outright, and a group is never published over a record with no party.

Vs. Seeker rematches come from the game's own rematch table in overlay 5, decoded
once and enumerated in full. Each 12-byte record is a base trainer ID followed by
five story-progress stage slots; a slot either names a distinct trainer record, is
marked as no upgrade at that tier, or is unused padding. The table's bounds are
taken from the code that reads it — four separate references resolve to its first
record and one to its end — rather than from a data scan, and decoding fails
outright unless the ROM satisfies the layout's invariants: unique base IDs, every
stage record referenced exactly once table-wide, and unused slots only ever
trailing. Chains that merely re-select their base encode a rematch with an
unchanged party and produce no variant family. Renegade Platinum's table is
byte-identical to retail, so it keeps the retail selector layout and needs no
profile override; only its parties differ.

Gym Leader and Elite Four rematch records are selected by different logic and are
not part of this table, so rematch and story-stage coverage remains partial. They
are not inferred from names, nearby IDs, levels, or party similarity.

## Locations

The map header table isn't a NARC archive in this generation — it's parsed
directly out of the ARM9 code binary at a fixed offset, one 24-byte record
per map. Each header holds: area data ID, matrix ID, script file ID, level
script ID, text archive ID, day/night music IDs, encounter-table ID, event
file ID, location-name ID, map-label window ID, weather ID, camera ID, and a
flags word (packed map-type/battle-background/permission bits, kept raw
rather than fully decoded). Internal map names come from a separate
fixed-size table (`fielddata/maptable/mapname.bin`).

Outdoor connections come from a separate `MapMatrix` archive
(`fielddata/mapmatrix/map_matrix.narc`) referenced by each header's own
matrix ID — the same underlying two-archive design (map headers plus a
separate matrix archive) Generation V's own Locations support reuses, just a
differently shaped record here: a variable-length member with an ASCII name,
an optional grid of real header IDs (for outdoor regions), and an optional
parallel altitude grid.

Visible field items (Item Balls) and hidden items (found via the Itemfinder)
are both decoded from map event data rather than the overworld-object records
Generation V uses: visible items are object events using the item-ball
graphics ID whose own script ID is a flat `7000 + item_id` offset, and hidden
items are background events of a specific event type whose script ID is a
flat `8000 + item_id` offset, each validated against the real item-name
table rather than assumed.

Presence in that event table does not by itself prove that a pickup is reachable:
a hack may leave an old event behind while changing the map or scripts. Location
pages therefore identify the rows as ROM item-event records and warn on origin
coordinates or unnamed item slots instead of silently presenting those records as
confirmed obtainable pickups. An item-ball/hidden-item event whose sprite or event
type marks it as a pickup but whose `script_id` offset doesn't resolve to a real
item is counted in the location dataset's own `unresolved_visible_item_count` and
`unresolved_hidden_item_count` rather than silently dropped.

Script-awarded items are kept separate from field pickups: an NPC's own dialogue
script can hand over an item directly, with no placed item-ball/hidden-item event
on the map at all. The field-script disassembler accepts reachable `AddItem`
commands whose item ID and quantity are both literal, and also a second,
control-flow-aware convention some scripts use instead: an if/elif-style NPC
(offering, say, a species-conditional held item, or a paid choice from a custom
shop menu) sets the item register differently in each mutually exclusive branch
before all of them converge on one shared `CallCommonScript` give-item call, so
resolving this correctly means walking the script's own control flow forward
from each literal item write to the call(s) it can actually reach, not just
checking the instruction immediately before the call. Only `CallCommonScript`
target IDs verified against a real item grant are accepted (confirmed for
Renegade Platinum: `2044` for a direct NPC gift and `2016` for a paid shop
purchase, verified exactly against Floaroma Town's "Item Fanatic" and two
custom shops), since the opcode is a general-purpose call reused by many
unrelated global routines. Reward shapes that resolve their item or quantity
some other way remain unavailable, so this is intentionally not a complete
obtainability guide.

Several bonus-encounter categories specific to this generation are decoded
from a separate archive (`arc/encdata_ex.narc`), not the main wild encounter
table: honey-tree header IDs (each offering common/uncommon/rare species
pools, taken directly from the game's own decompiled `HoneyTree_TryInteract`
header-ID table), Great Marsh header IDs sharing one daily species pool, and
Trophy Garden's own single header ID with its own daily pool. All of these
expose only what the ROM stores as fixed data — species pools, not which
entry is active on a given save file, since that's derived from save-file
state (a daily seed or save-persisted rotation) rather than a ROM fact.

Static encounters (see Items above) are attached to their real map locations
using the same script-file cross-reference mechanism trainer battles use.

## Text and names

Pokémon, ability, move, item, and location display names are decoded
directly from the ROM's own message archive by member index, rather than
from PokéDB. Trainer names, trainer class names, decoration names, seal
names, and NPC-trade nickname/OT-name text each have their own dedicated
member in the same archive. PokéDB supplies stable page slugs and links
without overriding any of these ROM-decoded names.

## Not yet available

The ROM's own Pokédex and move/ability/item description text banks aren't
extracted yet: this needs dedicated offset research of its own, so PokéDB's
effect description and flavor-text quote are shown instead, version-matched
to the profile's base game, while every structured mechanical field remains
ROM-derived and authoritative. This is the same gap Generation V's own
description text has, for the same reason.

Which honey-tree slathering yields, which four trees are a save file's
guaranteed Rare trees on a given file, and which Great Marsh/Trophy Garden
pool entries are live today are all derived from save-file state rather than
ROM data, so those specific, per-save selections are intentionally left
unrendered — the same policy that keeps Poké Radar chains and the dual-slot
"today's" pick unrendered elsewhere in this project.

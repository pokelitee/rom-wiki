## Pokémon species data

Personal records come from `a/0/1/6`. The first 709 archive members are
fixed 76-byte records: member 0 is the unused placeholder, members 1-649 are
National Pokédex species, members 650-684 are internal Pokéstar Studios
actors, and members 685-708 hold alternate or battle-only forms. The following
regional-Pokédex table is not treated as a personal record. Internal actors are
kept out of the public species catalog, while real forms are attached to their
base species with stable form identities.

The first 60 bytes retain the Black/White personal layout: base stats, types,
catch rate, base experience, EV yields, three wild-held-item slots, breeding
data, three ability slots, body color, sprite orientation, and the 101-bit
TM/HM compatibility mask. B2W2 appends 16 bytes of move-tutor compatibility.
Those flags are joined to the 60-entry tutor table in ARM9 overlay 36, including
each tutor's shard color, cost, and location.

Level-up learnsets (`a/0/1/8`), evolutions (`a/0/1/9`), and egg moves
(`a/1/2/4`) use the validated Generation V record formats shared with
Black/White. Every archive member is decoded independently and joined by its
personal-member identity; malformed sizes, missing terminators, invalid move
IDs, and incomplete evolution slots are rejected.

## Items

Item records come from `a/0/2/4`, one 36-byte record per archive member with
item ID mapping directly to member index. The record includes price, held and
consumable effects, pockets and usage flags, fling and Natural Gift behavior,
party-use effects, stat and EV changes, restoration values, and friendship
changes. B2W2's field-use function IDs are interpreted with the sequel's own
table rather than Black/White's labels.

Pickup uses the shared Generation V sliding-window table found by signature in
overlay 166. Its item order is ROM-derived; the fixed per-slot probabilities
are engine behavior and are identified as such rather than presented as stored
table values.

Script disassembly finds literal catchable wild battles, direct Pokémon and
egg gifts, and the fossil-revival item-to-species dispatch. Alternate rematch
levels for the same one-time encounter are collapsed to the initial encounter,
and non-catchable form-specific story battles are excluded. Static encounters
are linked back to maps through the same script ownership used by locations.

NPC trades come from `a/1/6/3`, one 108-byte record per member, with active
records selected separately for each version. Records supply offered and
requested species, form, fixed IVs, personality, OT details, and held item;
nicknames and OT names come from the ROM's trade text. The first 24 records are
the repeatable Curtis/Yancy trades and are published as Xtransceiver
interactions without a fixed map. The remaining fixed trades are linked through
map-owned text and common-script relationships.

Shop inventories come from `a/2/8/2`. The six badge-progression inventories
are separated from the sequel's location-specific shops. Script selectors
`0` through `25` select those local inventories, selectors `253` and `254`
select the Gear Station/PWT BP exchanges, and selector `255` selects the
standard Poké Mart. Black City's four conditional market stores are attached
to the city with their Black Tower requirement, daily limit, and weekday or
weekend stock.

## Moves

Move records come from `a/0/2/1`, one fixed 36-byte record per move ID. B2W2
retains the Black/White binary layout, covering effect, category, power, type,
accuracy, PP, secondary-effect chance, target, priority, and battle flags.
Move names are decoded separately from the message archive so a modified ROM's
own names remain authoritative.

## Wild encounters

Wild encounters come from `a/1/2/7` using the shared Generation V seasonal
format. A member contains either one 232-byte block or four consecutive blocks
for spring, summer, autumn, and winter. Each block stores encounter rates and
species/level slots for grass, dark grass, rustling grass, Surf, rippling-water
Surf, fishing, and rippling-water fishing. Fixed slot probabilities are engine
weights, not bytes stored in each record.

Encounter members are joined to real location names through map headers. The
same encounter member can therefore appear under multiple maps without being
duplicated or assigned a guessed location.

Hidden Grottos use their separate `a/2/7/3` archive. Each 220-byte member is
decoded independently for the profile's version half: three Pokémon pools store
species, minimum and maximum levels, female percentages, and forms, followed by
four visible-item pools and four hidden-item pools. The exterior map relationship
comes from furniture dispatch IDs `10795` through `10814`, which resolve all 20
archive members exactly once; archive order or location names are not used to
guess ownership. The reviewed dispatch base and member count are profile
contracts, so variants must opt into that exact band. Pool and group weights are engine rules rather than fields
stored alongside each slot.
Each verified exterior-map relationship is also used to show the Grotto as an
anchored section on its owning location page; it does not turn the Grotto pool
into ordinary grass or cave slots.

Daily Pokémon swarms come from an 18-record table in decompressed ARM9 overlay
36. Each
8-byte record stores a map-header ID, species ID, minimum and maximum level, and
zero padding. Black 2- and White 2-based profiles carry their own reviewed table
offset, so version-specific species are extracted independently and merge into
version tabs. The encoded header ID provides the location relationship directly.
The resulting swarm override is shown as an anchored section on that location
page while remaining a distinct normalized conditional encounter source.

## Trainers

Trainer headers come from `a/0/9/1` and parties from `a/0/9/2`. The shared
Generation V decoder reads each 20-byte header, then sizes its party records
from the stored held-item and custom-move flags. Party entries retain species
and form, stored level, IV strength, ability selection, forced gender, held items, and
custom moves where present; derived attributes remain distinguished from facts
stored in the ROM.

Unlike Black and White's trainer-name bank, the B2W2 bank retains entry zero.
Trainer names therefore use the trainer ID directly as their message index. This
leaf-specific rule prevents the one-record shift that previously labeled Skyla's
record as Burgh, Cheren's as Skyla, and Pokémon League records as the preceding
trainer.

The BW common-script band rule is reused unchanged for B2W2, verified
independently against real Black 2 ROM data rather than assumed to carry over:
resolving sight-triggered NPCs this way links 662 of 813 trainer records
(81%, up from 0), and the output is story-coherent, not coincidental — the
low trainer IDs walk a contiguous in-order path through the game's opening
routes and cities, correctly clustering the Castelia Sewers Team Plasma
ambush's three Elite Four members at that one location. Every trainer
resolving to more than three locations is independently explained, either as
Bianca (a rival who legitimately battles the player nine times) or as one of
ten "wandering trainer pool" NPCs that share one common script placed across
many maps, a known B2W2 design pattern.

A battle command is accepted when its trainer operands are valid and the command
that follows it is a real entry in this engine's opcode table. Requiring the
follow-on to be `TrainerBattleIsVictory` specifically had discarded two thirds
of the scripted battles: only 59 of the 180 sites with valid operands use it,
while the rest continue with `VMCall`, `VMJump`, or `WorkSetConst`, all of them
named commands. Correcting this raises resolved script references from 65 to 241
in Black 2, 65 to 287 in Blaze Black 2, and 123 to 351 in Redux, with no
previously resolved battle lost. The recovered records land where they should:
every Gym Leader in their own city — Cheren in Aspertia, Roxie in Virbank, Burgh
in Castelia, Elesa in Nimbasa, Clay in Driftveil, Skyla in Mistralton, Drayden
in Opelucid, Marlon in Humilau — and each Elite Four member's first and rematch
records in the same Pokémon League room. The eight Normal and Challenge Gym
records now resolve to the same city as each other in all eight cases, which
corroborates the difficulty dispatch pairs from a second, independent direction. Post-battle healing and
victory-item behavior remain exact header facts.

Starter-dependent Hugh battles are represented as three exact party tabs.
Retail and both supported hack families were ROM-checked independently; the Tepig
branch is retained even when its first record has an unrelated static trainer
name. Early, middle, late, and rematch triplets all reference their exact stored
parties rather than a synthesized rival record.

B2W2's Easy/Normal/Challenge selector is separate from the party member's
`iv_strength` byte. Runtime level adjustment applies to trainer battles generally;
alternate party records are related only where a verified dispatcher selects one.
Easy and Normal share the normal record for the documented Gym and Pokémon League
battles, while Challenge selects their alternate record. First-clear and rematch
Elite Four/Champion records are represented as distinct conditions. The engine
adjusts the displayed battle level after loading the party, but the
retail-compatible stat calculation continues using the stored record level—the
known level/stat bug. Retail, original Blaze Black 2/Volt White 2, and Redux
declare separate profile contracts; their exact normal and Challenge archive
records were checked independently. The complete executable level-offset band
table is still unresolved, so difficulty coverage remains partial and no numeric
per-record display level is guessed. Redux's Reversal Mountain Bianca teams are
also related explicitly from their decoded field-script selector:
Easy/Normal use trainer record 4 and Challenge uses record 852. Other apparent
same-name or three-record runs remain ungrouped unless their runtime selector is
independently verified.

N's Castle uses two independently verified selectors. The first battle selects
the Zekrom record in Black 2-based versions and the Reshiram record in White
2-based versions. Later rematches select records 782 through 785 for spring,
summer, autumn, and winter respectively. Retail research documents both rules,
and the exact parties were checked in each supported retail, original-hack, and
Redux ROM contract. These are rendered as two tab families rather than one
six-record same-name group.

## Locations

Map headers come from member 0 of `a/0/1/2`, one 48-byte record per map.
Headers provide matrix, script, text, encounter, and display-name references.
B2W2 packs flags into the upper four bits of the encounter field, so only the
low twelve bits form the archive index and `0xFFF` is null.

The location pipeline joins headers with overworld objects (`a/1/2/6`), map
matrices (`a/0/0/9`), field scripts (`a/0/5/6`), and ROM text. Location pages
publish bidirectional wild-encounter links, trainers, warps, outdoor matrix
connections, visible and hidden items, script-awarded items, static
encounters, trades, and shops. An overworld object with the shared item-ball
sprite whose `scriptUsed` doesn't resolve through the shared dispatch table
(see Black/White's own notes for that mechanism, shared by this engine) is
counted in the location dataset's own `unresolved_visible_item_count` rather
than silently dropped.

Script awards are reachable `ItemAdd` commands whose item ID and quantity are
both validated literals, plus the indirect `WorkSet`+`WorkSet`+`RTCallGlobal`
give-item convention some NPC gifts use instead -- this game shares Black/
White's own confirmed target-ID set (`2805`, `2806`, `2807`, `2814`; see that
profile's own notes), plus its own independent confirmation: `2814` against
Strange House's Lunar Wing gift. They retain script member and byte offset
and are rendered separately from pickups. Only `RTCallGlobal` target IDs
verified against a real item grant are accepted, since the opcode is a
general-purpose call reused by many unrelated global routines. Reward shapes
that resolve their item or quantity some other way remain unavailable -- this
is intentionally not a complete obtainability guide.

Common-script references use the sequel's own member-number mapping rather
than Black/White's mapping. This mapping is capped by the scripts archive's
own real size (1290 members): overworld NPCs whose `scriptUsed` selects a
member past that boundary (roughly 50 values across the game, clustered
almost entirely at named minigame set-pieces -- Musical Theater, Pokéstar
Studios, the Pokémon World Tournament, Gear Station) are not resolved by this
mapping and are not investigated further, since they read as several
unrelated per-minigame subsystems rather than one findable mechanism. One
such NPC (a recurring "Happiness Rater" placed at Icirrus City and reused,
via this same broken indirection, as an additional physical placement at a
handful of other routes) was checked directly: its real reward script is
Icirrus City's own dedicated script, already published under that location's
`script_awarded_items` (King's Rock, Cleanse Tag, and Exp. Share, gated on
party Pokémon happiness) -- so this specific feature's content is not
missing, only its duplicate placements at the other routes are unlisted.

## Text and names

Display names come from the ROM's message archive at `a/0/0/2`: Pokémon,
abilities, moves, items, trainers, trainer classes, locations, and NPC-trade
names each use the profile's verified member index. PokéDB contributes stable
slugs, links, descriptions, and available sprites without replacing decoded
ROM names or mechanics.

## Known coverage limitations

The ROM's Pokédex and move, ability, and item description banks are not yet
decoded, so those prose fields use version-matched PokéDB reference text while
structured mechanics remain ROM-derived. Outcomes controlled by save data or
runtime randomness are not presented as fixed ROM facts.

Hidden Grottos and daily swarms remain separate normalized sources from ordinary
seasonal area tables even though their tables are presented on their verified
location pages. The standard archive covers all seven ordinary methods, including dark
grass, rustling grass or dust clouds, rippling-water Surf, and rippling-water
fishing. Scripted static encounters, gifts, and trades are published separately
on location and Pokémon pages.

Tornadus and Thundurus are not roaming encounters in Black 2 or White 2. The
executable-code limitation documented for those roamers applies only to the
original Black and White games.

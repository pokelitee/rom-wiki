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

## Trainers

Trainer headers come from `a/0/9/1` and parties from `a/0/9/2`. The shared
Generation V decoder reads each 20-byte header, then sizes its party records
from the stored held-item and custom-move flags. Party entries retain species
and form, level, difficulty, ability selection, forced gender, held items, and
custom moves where present; derived attributes remain distinguished from facts
stored in the ROM.

Trainer locations are resolved from overworld objects that carry trainer IDs
and from literal battle commands in each map's scripts. Post-battle healing and
victory-item behavior are preserved where the script records them.

## Locations

Map headers come from member 0 of `a/0/1/2`, one 48-byte record per map.
Headers provide matrix, script, text, encounter, and display-name references.
B2W2 packs flags into the upper four bits of the encounter field, so only the
low twelve bits form the archive index and `0xFFF` is null.

The location pipeline joins headers with overworld objects (`a/1/2/6`), map
matrices (`a/0/0/9`), field scripts (`a/0/5/6`), and ROM text. Location pages
publish bidirectional wild-encounter links, trainers, warps, outdoor matrix
connections, visible and hidden items, static encounters, trades, and shops.
Common-script references use the sequel's own member-number mapping rather
than Black/White's mapping.

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

Tornadus and Thundurus are not roaming encounters in Black 2 or White 2. The
executable-code limitation documented for those roamers applies only to the
original Black and White games.

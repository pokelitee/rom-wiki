## Pokémon species data

Personal records are decoded from `a/0/0/2`. HeartGold and SoulSilver contain
508 fixed 44-byte records: 505 public species and battle forms plus three internal
records retained only in normalized audit data. Stats, types, held items, growth
data, ability slots, and TM/HM compatibility remain ROM-authoritative.

Level-up learnsets (`a/0/3/3`), evolutions (`a/0/3/4`), the combined egg-move
table (`a/2/2/9` member 0), and all 92 TM plus 8 HM assignments are decoded. The
machine table is found through a verified executable signature rather than a
build-specific absolute offset. Sacred Gold and Storm Silver retain these formats
and are decoded from their own patched archives.

## Items

The item archive at `a/0/1/7` contains 514 fixed 34-byte records. The executable's
item-to-archive mapping resolves named IDs outside the direct archive range, and
the public dataset exposes 513 nonzero item IDs without inventing records.

The in-game trade archive at `a/1/1/2` publishes 11 actual NPC exchanges. Shuckie
and Kenya are excluded because their records are gift-like static Pokémon rather
than trades. A unique executable signature resolves 27 supported specialty shops
with 141 item entries, published standalone (unlocated) as this site's marts
dataset. Shop labels are sourced from Ajarmar/universal-pokemon-randomizer-zx's
HGSS-specific `hgssShopNames` (`Gen4Constants.java`), distinct from that same
file's separate Platinum/Diamond-Pearl arrays. Several of that array's own
labels name Sinnoh locations that don't exist in HGSS's Johto/Kanto setting --
placeholder names in the source tool for shared byte-table slots holding no
valid HGSS data -- so those slots are excluded rather than published; every
published shop decodes to real, in-bounds item IDs under a real Johto/Kanto
location name, and its main-game/post-game flag matches HGSS's real Johto
(pre-Elite-Four) versus Kanto (post-Elite-Four) structure.

Separately, each map header's own decoded field-script mart-opening dispatch
commands (`MartBuy`, `SpecialMartBuy`, `DecorationMart`, `SealMart`) are now
published per location as a real, verified fact -- kind and raw inventory
selector, cross-referenced to their owning map header -- without claiming to
know what each mart sells. The inventory content those dispatch commands
reference is a separate, still-undecoded structure: an exhaustive search for
DPPT's equivalent ARM9-embedded inventory tables across HGSS's entire ARM9
binary and every overlay found no match, so this project does not invent
item lists for them.

Pickup uses two uniquely located tables in decompressed battle overlay 12. Its 18
common and 11 rare items expand into ten exact level bands whose probabilities
each total 100%. Retail and supported hacks independently decode their own tables.

## Moves

The move archive at `a/0/1/1` contains 471 fixed 16-byte records. The public
dataset exposes 467 playable moves and retains four internal records for audit.
Decoded mechanics include type, damage class, power, accuracy, PP, effect, target,
priority, battle flags, and contest fields.

The 52 regular move-tutor records come from decompressed overlay 1. Their packed
fields provide BP costs and tutor groups, including the free Headbutt tutor in
Ilex Forest. `fielddata/wazaoshie/waza_oshie.bin` supplies 505 eight-byte tutor
compatibility rows.

## Wild encounters

Wild encounters come from `a/0/3/7`. Retail HGSS contains 142 records of 196
bytes; Sacred Gold and Storm Silver use profile-authorized 192-byte records that
omit the final night-fishing and fishing-swarm replacement fields. Those missing
values remain unavailable rather than receiving retail defaults.

HGSS-specific decoding preserves morning, day, and night walking slots; Surf,
Rock Smash, and three rod tables; Hoenn and Sinnoh radio species; land and surf
swarms; and the optional night-fishing and fishing-swarm replacements. Slot
weights are taken from the engine's selection routines.

Headbutt encounters come from `a/2/5/2`, whose 540 members are indexed directly
by map header. An active member stores common, rare, and secret six-slot pools,
followed by six-coordinate tree groups terminated by `(-1, -1)`. The engine's
verified Headbutt slot weights are applied by slot position. Empty members are
validated as four-byte zero records, while active record sizes, species, levels,
group counts, terminators, and inactive pools are checked before publication.
HeartGold, SoulSilver, Sacred Gold, and Storm Silver each decode their own
archive rather than sharing retail records.
Because each active member is owned by an exact map header, Headbutt tables are
shown as an anchored section on that map's location page. The normalized
Headbutt records remain separate from ordinary wild-encounter records.

Safari Zone encounters come from `a/2/3/0`, with one member for each of the 12
named areas. Every member starts with five block-encounter counts, then stores
ten base slots for morning, day, and night for Grass, Surf, and all three rods.
Each block-conditioned record stores the same three time-of-day outcomes plus
up to two `(block category, count)` requirements. Exact member sizes, header and
slot padding, species, levels, block categories, and requirement pairs are
validated independently in all four supported profiles. The two requirements
are preserved as stored; the pages do not invent replacement priority that is
not encoded in the archive.
Safari areas are not assigned to fixed map headers: the player can place the 12
areas dynamically. They are therefore presented together on one anchored Safari
Zone encounter page rather than attached to guessed location pages. The
zone's 14 physical maps (decoded, literal map-header facts) are cross-linked
to that page and back, without claiming which area currently occupies which
map.

## Trainers

Trainer records (`a/0/5/5`) and parties (`a/0/5/6`) contain 738 members. Member 0
is unused, so 737 trainers are published. Names, classes, class genders, flags,
battle items, AI settings, battle type, party species and forms, levels, held
items, and custom moves are ROM-derived.

Starter-variable branches are decoded from each profile's scripts. HGSS shares
Platinum's compare-and-branch idiom but uses its own trainer-battle opcode. A
branch is accepted only when it compares against a species from that profile's
decoded starter table and leads to a valid trainer record; nothing is inferred
from trainer names, adjacent IDs, levels, or party similarity. This applies to
retail HGSS and the supported Sacred Gold/Storm Silver profiles.

Trainer-class payout multipliers remain unavailable because Platinum's locator
does not occur in HGSS and no unique HGSS table reference is established. The
phone-rematch state machines remain undecoded.

Talk-triggered trainer battles are joined from literal `CallTrainerBattle`
field-script commands, the same way as other Generation IV profiles, but
using HGSS's own opcode (`0x00D5`, distinct from Platinum's `0x00E5`) rather
than assuming Platinum's numbering carries over. This links every Gym
Leader, Elite Four member, and the Champion to both their first battle and
their Kanto Gym Leader Rematch Tour location.

Trainer records without a verified literal overworld or script reference show
no location. Their exact parties are still published; no location or variant
relationship is inferred from names, nearby IDs, or party composition.

## Locations

The event archive at `a/0/3/2`, matrix archive at `a/0/4/1`, and 540 packed ARM9
map headers provide location identities, 1,317 warps, 158 directional connections,
and nine explicitly dynamic warps. Destination bounds and destination-warp
existence are validated before publication.

Event objects link trainer IDs to map headers through HGSS's verified
`script_id - 3000 + 1` convention. Visible and hidden item events are decoded
from each ROM rather than copied between retail and hack profiles. An
item-ball/hidden-item event whose sprite or event type marks it as a pickup
but whose `script_id` offset doesn't resolve to a real item is counted in the
location dataset's own `unresolved_visible_item_count` and
`unresolved_hidden_item_count` rather than silently dropped.

Visible item-ball placements resolve through this engine's own shared
dispatch table rather than the flat `script_id - 7000 = item ID` shortcut
Generation IV's Platinum-based engine uses: `script_id` selects one of 256
functions in one shared script member (verified against `pret/pokeheartgold`'s
public decompilation of vanilla HeartGold/SoulSilver, `src/script_manager.c`'s
`sScriptBankMapping` -- confirmed stable across retail HeartGold, SoulSilver,
and the Sacred Gold/Storm Silver hacks, identical member index and size in
all four), and each function stages the real item ID and quantity into two
scratch variables before falling through to a shared give-item tail. This
table is **not** an identity mapping: cross-checked function-by-function
against `pret/pokeheartgold`'s own `std_itemball_*` naming constants (e.g.
function 0 is `std_itemball_r29_potion` and decodes to item 17/Potion,
function 4 is `std_itemball_r31_poke_ball` and decodes to item 4/Poké Ball --
matched exactly for the first nine functions checked), the flat shortcut had
been silently resolving the large majority of item-ball placements to the
wrong item, across every HGSS-family profile including unmodified retail
HeartGold/SoulSilver, undetected until this table was decoded and compared
against it directly. Sacred Gold/Storm Silver additionally repurpose specific
table entries for hack-added items (e.g. Woodland Ore, Serenade Orb), which
were affected the same way. Every item-ball placement is now decoded through
the real table.

Hidden-item placements are a *different* mechanism from item balls, not a
variant of the same one, and had the identical class of bug independently:
the game's own field-script dispatch for hidden items (`script_id - 8000`)
collapses to a single shared function reused by every hidden item, which
itself reads the real item and quantity from a native ARM9 data table
(`sHiddenItemParam` in `pret/pokeheartgold`'s decompilation) searched by
index rather than a per-index script function -- so the flat
`script_id - 8000 = item ID` shortcut was exactly as wrong here as it was for
item balls, for the same reason. Located in each ROM by the table's own
distinctive leading records rather than a per-profile offset, and decoded
until a record fails basic structural validity. Verified against real ROM
data: all 231 real HeartGold entries matched `pret/pokeheartgold`'s own
decompiled table with zero mismatches, and Sacred Gold/Storm Silver's table
is byte-for-byte identical to retail's (unlike item balls, this hack does not
edit hidden items). Every hidden-item placement is now decoded through the
real table.

Script-awarded items are kept separate from field pickups: an NPC's own
dialogue script can hand over an item directly, with no placed item-ball/
hidden-item event on the map at all. This uses the same control-flow-aware
`CallCommonScript` convention documented for the Platinum-based engine (see
that profile's own notes), but under this engine's own confirmed target ID,
`2033` (`std_give_item_verbose` in `pret/pokeheartgold`'s decompiled
constants) -- verified against seven real NPC gifts across Sacred Gold
(TM70 at Sprout Tower, TM35, TM24, TM13, TM29, Magma Stone, and Earth Plate),
each at the map location its literal item/quantity operands point to.
`CallCommonScript` target IDs are assigned independently per engine leaf
(Platinum and HeartGold/SoulSilver do not share one ARM9 codebase), so this
ID is not assumed to carry over to or from the Platinum-based engine.

Sacred Gold/Storm Silver's own "Covenant Orb" (documented as automatically
awarded after completing any in-game trade) was checked for a native ARM9
hook and none was found: the literal item ID never appears as a script-award
operand anywhere in the script archive (checked with the same
control-flow-aware scanner as the confirmed grants above), Sacred Gold's main
ARM9 binary differs from vanilla HeartGold's in only a handful of small
regions (data tables, not code, and none item-ID-shaped), and all 200 checked
overlay IDs are byte-identical to vanilla HeartGold. This item's real grant
mechanism, if any exists in this specific ROM build, is not reachable by any
extraction method this project currently has, so it is not published as
obtainable rather than guessed at.

Battle-triggered static encounters (`WildBattle`) are decoded and published as
each map header's `static_encounters`, using a ground-truth field-script
opcode table (`gen4/hgss/script_opcode_table.py`, sourced from
pret/pokeheartgold's real decompilation, not an inferred walker). A literal
`WildBattle`
site is accepted only when its species/level operands are in range and its
result is validated by a real follow-on command (`CheckBattleWon`, directly
or after a `ClearFlag`) -- see `gen4/hgss/scripts.py`'s module comment for
the full verification, including a cross-check against every resulting
site's real-world identity (every HeartGold/SoulSilver hit is a known,
named legendary or gift encounter; Sacred Gold/Storm Silver's additional
hits match that hack's own documented legendary/gift additions).

Direct-to-party gifts (`GiveMon`, `GiveEgg`, and `GiveTogepiEgg`) are
published as each map header's `pokemon_gifts`. Only call sites reachable from
real script code are accepted, then species and level operands must be in range;
each `GiveEgg` is also preceded by a `BufferSpeciesName` naming the same
species. `GiveTogepiEgg` has no species operand, so its species is resolved from
the ROM's own Pokémon name table. Common-script-routed gifts and eggs, and
variable-backed operands, remain unresolved.

## Text and names

Names and descriptions are decoded from each ROM's message archive at `a/0/2/7`.
Move, ability, and item descriptions are members 749, 722, and 221. Both
versions carry both Pokédex texts; HeartGold reads member 803 and SoulSilver
member 804, which match each version's published Pokédex.
The relevant member tables are validated against the engine's record counts before
use. PokéDB supplies canonical links, descriptive metadata, and optional media
fallbacks; it does not replace ROM-derived mechanics or provide the clean
comparison baseline.

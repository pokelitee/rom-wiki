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
with 141 item entries. Shop map placement remains unavailable because the
corresponding HGSS script commands have not been decoded.

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
phone-rematch state machines and some alternate trainer-battle command shapes
also remain undecoded.

Trainer records without a verified literal overworld or script reference remain
listed as Unlinked. Their exact parties are still published; no location or
variant relationship is inferred from names, nearby IDs, or party composition.

## Locations

The event archive at `a/0/3/2`, matrix archive at `a/0/4/1`, and 540 packed ARM9
map headers provide location identities, 1,317 warps, 158 directional connections,
and nine explicitly dynamic warps. Destination bounds and destination-warp
existence are validated before publication.

Event objects link trainer IDs to map headers through HGSS's verified
`script_id - 3000 + 1` convention. Visible and hidden item events are decoded
from each ROM rather than copied between retail and hack profiles.

Static encounters, gifts and eggs, Headbutt tree tables, and Safari Zone block
configuration remain explicit limitations. Their files or some retail offsets are
known, but their complete HGSS semantics and hack-safe map associations are not
decoded into normalized contracts.

## Text and names

Names and descriptions are decoded from each ROM's message archive at `a/0/2/7`.
The relevant member tables are validated against the engine's record counts before
use. PokéDB supplies canonical links, descriptive metadata, and optional media
fallbacks; it does not replace ROM-derived mechanics or provide the clean
comparison baseline.

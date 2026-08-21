from __future__ import annotations

# Generation III's personal-info struct (`gBaseStats` in the public
# pokefirered/pokeemerald decompilations) is a fixed 28-byte record with no
# inline TM/HM compatibility bitmap -- that lives in a separate
# `gTMHMLearnsets` table, out of scope until the machines concern is added.
PERSONAL_RECORD_SIZE = 28

# FireRed/LeafGreen's personal-info table actually holds 412 entries
# (verified against the real ROM -- see personal_offset in the profile
# TOML): a dummy record at index 0, National Dex species 1-386, then
# non-species padding (Egg/Unown-letter/Deoxys-forme slots per the public
# pokefirered decompilation) through index 411. Bounded here to 386 -- the
# National Dex range PokeDB can actually resolve a slug/reference for --
# until the padding range's per-index slugs are confirmed and added to
# PERSONAL_INTERNAL_MEMBERS/PERSONAL_FORM_MEMBERS below.
PERSONAL_RECORD_COUNT = 386

# Generation III kept the reserved "???" (Mystery) type slot at index 9
# that Generation IV also still had (removed only when Fairy was added in
# Generation VI) -- identical ordering to `engines/gen4/constants.py`'s own
# table, kept as a separate literal here rather than imported across engine
# leaves per this repo's package-boundary rule.
TYPE_NAME_COUNT = 18
TYPE_NAMES = (
    "normal",
    "fighting",
    "flying",
    "poison",
    "ground",
    "rock",
    "bug",
    "ghost",
    "steel",
    "unknown",
    "fire",
    "water",
    "grass",
    "electric",
    "psychic",
    "ice",
    "dragon",
    "dark",
)

# Unchanged from Generation IV/V's identical engine-internal ID scheme.
EGG_GROUP_NAMES = (
    "none",
    "monster",
    "water-1",
    "bug",
    "flying",
    "field",
    "fairy",
    "grass",
    "human-like",
    "water-3",
    "mineral",
    "amorphous",
    "water-2",
    "ditto",
    "dragon",
    "undiscovered",
)
GROWTH_RATE_NAMES = (
    "medium-fast",
    "erratic",
    "fluctuating",
    "medium-slow",
    "fast",
    "slow",
)

# `pipeline/enrichment/names.py`'s resolve_*_names helpers read these
# unconditionally (before checking whether the raw dataset actually carries
# the corresponding ROM-derived name table), even though reference-name
# extraction isn't implemented for every domain yet. Zero rather than a
# guessed real count, so nothing here looks like a verified fact it isn't.
# MOVE_NAME_COUNT is real now that the moves domain is implemented.
# ITEM_NAME_COUNT is real (matches ITEM_RECORD_COUNT below) now that
# `pipeline/extraction/trainers/pointer_party.py` decodes item display
# names for held/AI-battle/victory item resolution (see that module's
# `_item_names` docstring). ABILITY_NAME_COUNT is real (see below) now that
# the abilities domain is implemented -- the rest stay zeroed until their
# own domains land.
ITEM_NAME_COUNT = 375
POKEMON_NAME_COUNT = 0
POKEMON_DESCRIPTION_COUNT = 0

# Verified against the real FireRed and LeafGreen ROMs (ability-name table
# at `ability_name_offset` in the profile TOML; index 0 is a "?"-decoded
# placeholder, index N = ability ID N). Decoded 12 consecutive entries
# against the real, unmistakable Generation III ability ID order (Stench,
# Drizzle, Speed Boost, Battle Armor, Sturdy, Damp, Limber, Sand Veil,
# Static, ...). The ROM table actually runs through index 77 ("AIR LOCK";
# index 78 onward decodes to garbage), but index 76 decodes to "CACOPHONY"
# -- a real, verified ROM entry with no PokeDB counterpart (PokeDB's ability
# numbering has no gap for it, so its own Air Lock is id 76, not 77 -- a
# one-entry numbering divergence starting exactly at Cacophony). Scanning
# every currently-decoded species (1-386, see PERSONAL_RECORD_COUNT) found
# no Pokemon referencing ability_id 76 or 77 in this ROM's data, so bounding
# the exposed table at 76 (abilities 1-75) loses no currently-displayed
# fact; revisit once the padding species range (387-411) is confirmed and
# exposed, since species 406 does reference Air Lock (77).
ABILITY_NAME_COUNT = 76

# Verified against the real FireRed and LeafGreen ROMs (move-data table at
# `move_offset` in the profile TOML; index 0 is an all-zero placeholder
# record, index N = move ID N). Move 354 (Psycho Boost) is the last real
# Generation III move.
MOVE_RECORD_SIZE = 12
MOVE_RECORD_COUNT = 355
MAX_MOVE_ID = 354

# The move-name table (`move_name_offset`/`move_name_stride` in the profile
# TOML) is a separate fixed-width array, one entry per move ID, distinct
# from the move-data table above -- verified against the real ROMs by
# decoding move 1 ("POUND"), move 33 ("TACKLE"), and move 354 ("PSYCHO
# BOOST") and confirming an exact match.
MOVE_NAME_COUNT = 355

# Generation III's move struct has no explicit damage-class byte (see
# moves.py) -- damage class is derived from power/type, but
# `pipeline/enrichment/moves.py` still needs the display-name table for
# whichever of these three IDs `moves.py` computes. Same ordering as
# `engines/gen5/bw/constants.py`'s identical table.
DAMAGE_CLASS_NAMES = ("status", "physical", "special")

# Verified against the real FireRed and LeafGreen ROMs (item table at
# `item_offset` in the profile TOML; index 0 is an all-"?" placeholder
# record, index N = item ID N). Item 374 (Sapphire) is the last real item.
ITEM_RECORD_SIZE = 44
ITEM_RECORD_COUNT = 375

# Verified against nine real items spanning every pocket: Potion/Antidote/
# Rare Candy/Repel decode to 1, Bicycle/Town Map to 2, Master Ball/Ultra Ball
# to 3, TM01 to 4, Oran Berry/Cheri Berry to 5 -- an exact match for
# FireRed/LeafGreen's five real Bag pockets in that order. Index 0 is unused
# (no real item has field_pocket_id 0).
ITEM_POCKET_NAMES = (
    "none",
    "items",
    "key-items",
    "poke-balls",
    "tm-hm",
    "berries",
)

# Verified against the real ROM (see personal.py): species 0 is an all-zero
# placeholder record, not a real Pokemon -- matches the same {0: "none"}
# convention `engines/gen5/bw/constants.py`'s PERSONAL_INTERNAL_MEMBERS uses.
# FRLG's personal table also has non-species padding near the end (species
# 387-411, likely Egg/Unown-letter/Deoxys-forme slots per the public
# pokefirered decompilation), but which slug maps to which index hasn't been
# verified against a real ROM yet, so none are listed here rather than
# guessing -- add them once confirmed, following this same pattern.
PERSONAL_INTERNAL_MEMBERS: dict[int, str] = {0: "none"}
PERSONAL_FORM_MEMBERS: dict[int, str] = {}

# Unchanged body-color ID scheme across Generation III-V (verified: Bulbasaur
# decodes to body_color_id=3 here, matching this table's "green" -- Bulbasaur
# is documented as Green in every generation's Pokedex color field). Kept as
# a separate literal rather than imported across engine leaves per this
# repo's package-boundary rule -- see `engines/gen5/bw/constants.py`'s
# identical table.
COLOR_NAMES = (
    "red",
    "blue",
    "yellow",
    "green",
    "black",
    "brown",
    "purple",
    "gray",
    "white",
    "pink",
    "internal",
)

# Verified against the real FireRed and LeafGreen ROMs (trainer table at
# `trainer_offset` in the profile TOML; index 0 is an all-zero-except-
# terminator dummy record, index N = trainer ID N). Index 742 ("PAXTON") is
# the last real trainer -- index 743 onward decodes to garbage, confirming
# the boundary.
TRAINER_RECORD_SIZE = 0x28
TRAINER_RECORD_COUNT = 743

# Verified against the real FireRed and LeafGreen ROMs (wild-encounter
# header table at `encounter_offset` in the profile TOML, one entry per
# map). Header 0's fields are `mapGroup`/`mapNum` (not a species/trainer-
# style index), so there's no dummy placeholder record the way personal/
# move/item/trainer tables have -- the table is simply 132 real entries,
# terminated by a `{0xFF, 0xFF, ...}` sentinel immediately after (matches
# the public pret decompilation's documented convention).
ENCOUNTER_HEADER_SIZE = 20
ENCOUNTER_HEADER_COUNT = 132

# Verified against real decoded data: map group 3 / map 22 (FireRed and
# LeafGreen both) decodes to a 12-slot land table (Spearow/Rattata/Ekans-or-
# Sandshrew/Mankey at levels 6-12), a 5-slot water table (Tentacool at
# levels 5-40), and a 10-slot fishing table (Magikarp/Horsea/Gyarados/
# Krabby/Psyduck at levels 5-35) -- real, sane Kanto encounter data, not
# structurally-plausible noise. Rock Smash wasn't present on this
# particular map but shares the water table's slot count per the public
# pokefirered decompilation's `WILD_TABLE_ROWS`.
ENCOUNTER_LAND_SLOT_COUNT = 12
ENCOUNTER_WATER_SLOT_COUNT = 5
ENCOUNTER_ROCK_SMASH_SLOT_COUNT = 5
ENCOUNTER_FISHING_SLOT_COUNT = 10

ENCOUNTER_METHOD_NAMES = ("land", "water", "rock_smash", "fishing")

# Fixed game-design percentages, not ROM-derived -- unchanged since
# Generation III introduced the wild-encounter slot system (per public
# "Wild Pokemon" mechanics documentation, e.g. Bulbapedia): land/water
# slot-chance sequences are identical to the ones Generation IV/V still use
# (`engines/gen4/dppt/encounters.py`'s GEN4_WALKING_SLOT_CHANCES/
# GEN4_WATER_SLOT_CHANCES), confirming they're a Generation III original,
# not a later-generation change. Rock Smash reuses the same 5-slot
# percentages as water (both are 5-slot tables introduced together in
# Generation III, before Generation IV HGSS later shrank Rock Smash to a
# 2-slot table -- see `engines/gen4/hgss/encounters.py`'s
# HGSS_ROCK_SMASH_SLOT_CHANCES for that later, different shape). Fishing is
# the documented per-rod sequence (Old Rod 70/30, Good Rod 60/20/20, Super
# Rod 40/40/15/4/1) concatenated into one 10-slot table, matching how a
# single `fishingMonsInfo` struct holds all three rods' slots together in
# this generation (unlike Generation IV+, which splits each rod into its
# own separate method).
ENCOUNTER_LAND_SLOT_CHANCES = (20, 20, 10, 10, 10, 10, 5, 5, 4, 4, 1, 1)
ENCOUNTER_WATER_SLOT_CHANCES = (60, 30, 5, 4, 1)
ENCOUNTER_ROCK_SMASH_SLOT_CHANCES = (60, 30, 5, 4, 1)
ENCOUNTER_FISHING_SLOT_CHANCES = (70, 30, 60, 20, 20, 40, 40, 15, 4, 1)

# `MapHeader` (`struct MapHeader`, `include/global.fieldmap.h` in the public
# pokefirered decompilation) is a fixed 28-byte record -- verified against
# real ROM data by decoding the confirmed segments below and cross-checking
# each header's `regionMapSectionId` against the region-name table.
MAP_HEADER_SIZE = 28

# The Town Map region-name table is a *separate*, variable-length,
# back-to-back 0xFF-terminated string table (see `text.py`'s
# `decode_gen3_text_sequence`), not one fixed-stride array like every other
# name table in this engine. Verified complete at exactly 109 entries for
# both FireRed and LeafGreen (index 0 = "PALLET TOWN" ... index 108 =
# "CELADON DEPT."; the byte immediately after index 108's terminator is
# unambiguous non-text graphics data, not a 110th entry).
MAP_HEADER_REGION_COUNT = 109

# `gMapGroups` itself (as opposed to `map_header_segments`' already-resolved
# `MapHeader` arrays) is a small array of pointers, one per map group, each
# pointing to that group's own contiguous array of pointers-to-`MapHeader`.
# Verified against real ROM code: the ARM7/ARM9-style Thumb routine at ROM
# address 0x08055238 in both games (`gMapGroups[group][num]`, an identical
# two-level-indirection double `ldr` chase) loads this exact base via a
# `ldr r2, [pc, #0xc]` literal pool value -- confirmed byte-for-byte at file
# offset 0x05524C (FireRed: `a8 26 35 08`; LeafGreen: `88 26 35 08`).
# Walking forward from that base until an invalid pointer is hit gives
# exactly 43 groups for both games (the 43rd entry, at `gmapgroups_offset +
# 43*4`, decodes to a small non-pointer integer, not a 44th valid address).
# Used only to backfill `locations` on wild-encounter records that fall
# within the already-verified Sevii Islands/postgame `map_header_segments`
# span -- every group/map slot outside that span (Kanto's own maps) has no
# corresponding entry in `map_header_segments` and is left unlinked, the
# same documented gap as `locations.py`'s module comment.
GMAPGROUPS_GROUP_COUNT = 43

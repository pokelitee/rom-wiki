from .constants import (
    ABILITY_NAME_COUNT,
    COLOR_NAMES,
    DAMAGE_CLASS_NAMES,
    EGG_GROUP_NAMES,
    EVOLUTION_METHOD_NAMES,
    EVOLUTION_PARAMETER_KINDS,
    GEN5_BASE_SPECIES_COUNT,
    GEN5_MACHINE_COUNT,
    GEN5_MACHINE_TABLE_PREFIX,
    GROWTH_RATE_NAMES,
    ITEM_NAME_COUNT,
    MAX_MOVE_ID,
    MOVE_NAME_COUNT,
    MOVE_RECORD_COUNT,
    PERSONAL_FORM_MEMBERS,
    PERSONAL_INTERNAL_MEMBERS,
    PERSONAL_RECORD_COUNT,
    PERSONAL_TRANSFORMATION_MEMBERS,
    POKEMON_NAME_COUNT,
    TRAINER_COSMETIC_FORM_LABELS,
    TRAINER_FORM_SLUGS,
    TYPE_NAME_COUNT,
    TYPE_NAMES,
)
from .disassembler import disassemble_function, parse_function_offsets
from .egg_moves import parse_egg_move_set
from .encounters import (
    METHOD_NAMES as ENCOUNTER_METHOD_NAMES,
)
from .encounters import (
    METHOD_SLOT_CHANCES as ENCOUNTER_METHOD_SLOT_CHANCES,
)
from .encounters import parse_encounter_entry
from .evolutions import parse_evolution_record
from .items import (
    GEN5_ITEM_FIELD_USE_NAMES,
    GEN5_ITEM_POCKET_NAMES,
    NATURAL_GIFT_TYPE_NONE,
    parse_item_record,
)
from .learnsets import parse_level_up_learnset
from .locations import (
    parse_map_header_script_files,
    parse_map_header_table,
    parse_map_header_text_files,
    parse_wild_map_names,
)
from .machines import machine_name, parse_machine_move_table
from .map_matrices import parse_map_matrix
from .marts import (
    SHOP_SELECTOR_TO_INVENTORY_ID,
    STANDARD_SHOP_SELECTOR,
    Gen5SpecialVendor,
    parse_shop_catalog,
    parse_shop_dispatch,
    resolve_special_vendor,
)
from .messages import parse_english_message_archive
from .moves import parse_move_record
from .overworld import (
    parse_overworld_furniture,
    parse_overworld_npcs,
    parse_overworld_warps,
    resolve_common_script_member,
    resolve_common_script_trainer_id,
    resolve_hidden_item_id,
    resolve_visible_item_id,
)
from .personal import parse_personal_record
from .pickup import (
    PICKUP_LEVEL_RANGE_COUNT,
    PICKUP_LEVEL_RANGE_SIZE,
    PICKUP_SLOT_CHANCES,
    PICKUP_TABLE_LOCATOR,
    parse_pickup_table,
    pickup_level_range_item_ids,
)
from .scripts import (
    find_fossil_revival_script,
    parse_fossil_revival_table,
    parse_trainer_battle_commands,
)
from .static_encounters import discover_static_encounters
from .trades import parse_npc_trade_record
from .trainer_party import (
    derive_trainer_party_attributes,
    normalize_trainer_party_member,
)
from .trainers import parse_trainer_record

# EngineAdapter's shared attribute surface -- see docs/development/adding-a-game.md.
# This engine currently implements the Pokémon personal-data, Items, Moves,
# Learnsets, Evolutions, Egg moves, TM/HM machines, Wild encounters, Trainers,
# Static encounters, Pickup, Marts, and Locations slices. Adding a
# later slice should add the corresponding module and re-export here, the
# same way these slices added personal.py/machines.py/items.py/moves.py/
# learnsets.py/evolutions.py/egg_moves.py/encounters.py/trainers.py/
# locations.py/static_encounters.py/pickup.py/constants.py.
# Move tutors are not a gap to fill in: Ajarmar/universal-pokemon-randomizer-zx's
# Gen5RomHandler.hasMoveTutors() returns true only for Black 2/White 2 --
# tutors were introduced in the sequels and don't exist in this release at all.
# Wild encounters attach real display names via `locations.py`'s small
# fixed-record map header table (`a/0/1/2`) -- messages.py's `_VARIABLE_MARKER`
# handling was needed first, since one (unused) entry in the map-name table
# contains a runtime-substituted-text control code that used to make the
# whole table fail to decode.
# Locations combine the map header, matrix, overworld-object, and field-script
# archives to resolve navigation, items, encounters, trainers, and shops.
# Trainers' map-location/script-reference linking, previously blocked on
# "this generation's script-engine
# opcode table hasn't been researched," is now unblocked: scripts.py adopts
# FrostFalcon/FrostsGen5Editor's BW1 field-script opcode table (an actively-
# maintained community tool, cross-checked against real ROM bytes -- see
# scripts.py's module docstring) to find literal `CallTrainerBattle`
# invocations the same "opcode signature + validating follow-on command" way
# gen4/dppt/scripts.py already finds Platinum's `StartTrainerBattle`, and
# overworld.py resolves sight-triggered battles' trainer IDs directly from
# the overworld NPC record's own `scriptUsed` field via a verified band
# arithmetic (see overworld.py's module docstring). Both are literal-ID-only;
# battles whose trainer can't be resolved to a real record are left unlinked
# rather than guessed at.
# Static (gift/single-Pokémon) encounters are discovered from reachable
# `CallWildBattle`/`PokePartyAdd` instructions. Fossil choices use the same
# validated comparison pattern as item enrichment, so BW profiles need no
# per-encounter script addresses.
# Roaming Pokémon (Thundurus/Tornadus) were investigated the same way and
# found to be a genuine exception: the unmodified retail ROM stores an ARM
# instruction, not a data word, at the "species" offset the randomizer's own
# ini lists for at least one of the two (verified against the real Black
# ROM) -- the real species is only a literal fact after the randomizer's own
# ASM patch is applied, so it's left undecoded here rather than guessed at.
# Pickup's item table (pickup.py) is found the same way the TM/HM move table
# is (machines.py): a byte-pattern search in an overlay, since it has no
# stable absolute offset across ROM builds -- no script-engine research
# needed here either. The per-level-range percentages themselves aren't ROM
# data, though; they're the same fixed engine formula Generation IV's own
# Pickup already uses (`PICKUP_SLOT_CHANCES`).
BASE_SPECIES_COUNT = GEN5_BASE_SPECIES_COUNT
INTERNAL_MEMBERS = PERSONAL_INTERNAL_MEMBERS
FORM_MEMBERS = PERSONAL_FORM_MEMBERS
TRANSFORMATION_MEMBERS = PERSONAL_TRANSFORMATION_MEMBERS
MACHINE_COUNT = GEN5_MACHINE_COUNT
MACHINE_TABLE_LOCATOR = GEN5_MACHINE_TABLE_PREFIX
# Consumed generically by pipeline/items.py (keyed off attribute name, not
# per-engine branching), matching Gen4's own `ITEM_POCKET_NAMES`/
# `ITEM_FIELD_USE_NAMES` precedent.
ITEM_POCKET_NAMES = GEN5_ITEM_POCKET_NAMES
ITEM_FIELD_USE_NAMES = GEN5_ITEM_FIELD_USE_NAMES

__all__ = [
    "ABILITY_NAME_COUNT",
    "BASE_SPECIES_COUNT",
    "COLOR_NAMES",
    "DAMAGE_CLASS_NAMES",
    "EGG_GROUP_NAMES",
    "ENCOUNTER_METHOD_NAMES",
    "ENCOUNTER_METHOD_SLOT_CHANCES",
    "EVOLUTION_METHOD_NAMES",
    "EVOLUTION_PARAMETER_KINDS",
    "FORM_MEMBERS",
    "GEN5_BASE_SPECIES_COUNT",
    "GEN5_MACHINE_TABLE_PREFIX",
    "GROWTH_RATE_NAMES",
    "INTERNAL_MEMBERS",
    "ITEM_FIELD_USE_NAMES",
    "ITEM_NAME_COUNT",
    "ITEM_POCKET_NAMES",
    "MACHINE_COUNT",
    "MACHINE_TABLE_LOCATOR",
    "NATURAL_GIFT_TYPE_NONE",
    "MAX_MOVE_ID",
    "MOVE_NAME_COUNT",
    "MOVE_RECORD_COUNT",
    "PERSONAL_FORM_MEMBERS",
    "PERSONAL_INTERNAL_MEMBERS",
    "PERSONAL_RECORD_COUNT",
    "PERSONAL_TRANSFORMATION_MEMBERS",
    "POKEMON_NAME_COUNT",
    "TRAINER_COSMETIC_FORM_LABELS",
    "TRAINER_FORM_SLUGS",
    "TRANSFORMATION_MEMBERS",
    "TYPE_NAME_COUNT",
    "TYPE_NAMES",
    "derive_trainer_party_attributes",
    "disassemble_function",
    "discover_static_encounters",
    "find_fossil_revival_script",
    "machine_name",
    "normalize_trainer_party_member",
    "parse_egg_move_set",
    "parse_encounter_entry",
    "parse_english_message_archive",
    "parse_evolution_record",
    "parse_fossil_revival_table",
    "parse_function_offsets",
    "parse_item_record",
    "parse_level_up_learnset",
    "parse_machine_move_table",
    "parse_map_header_script_files",
    "parse_map_header_text_files",
    "parse_map_header_table",
    "parse_map_matrix",
    "parse_move_record",
    "parse_overworld_furniture",
    "parse_overworld_npcs",
    "parse_overworld_warps",
    "parse_personal_record",
    "parse_npc_trade_record",
    "parse_pickup_table",
    "parse_shop_catalog",
    "parse_shop_dispatch",
    "resolve_special_vendor",
    "parse_trainer_battle_commands",
    "parse_trainer_record",
    "pickup_level_range_item_ids",
    "resolve_hidden_item_id",
    "resolve_visible_item_id",
    "SHOP_SELECTOR_TO_INVENTORY_ID",
    "STANDARD_SHOP_SELECTOR",
    "Gen5SpecialVendor",
    "PICKUP_LEVEL_RANGE_COUNT",
    "PICKUP_LEVEL_RANGE_SIZE",
    "PICKUP_SLOT_CHANCES",
    "PICKUP_TABLE_LOCATOR",
    "parse_wild_map_names",
    "resolve_common_script_trainer_id",
    "resolve_common_script_member",
]

from romwiki.engines.gen5.shared.constants import (
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
    INTERNAL_TO_NATIONAL_DEX,
    MAX_MOVE_ID,
    MOVE_NAME_COUNT,
    MOVE_RECORD_COUNT,
    TYPE_NAME_COUNT,
    TYPE_NAMES,
)
from romwiki.engines.gen5.shared.egg_moves import parse_egg_move_set
from romwiki.engines.gen5.shared.encounters import (
    METHOD_NAMES as ENCOUNTER_METHOD_NAMES,
)
from romwiki.engines.gen5.shared.encounters import (
    METHOD_SLOT_CHANCES as ENCOUNTER_METHOD_SLOT_CHANCES,
)
from romwiki.engines.gen5.shared.encounters import parse_encounter_entry
from romwiki.engines.gen5.shared.evolutions import parse_evolution_record
from romwiki.engines.gen5.shared.items import (
    GEN5_ITEM_FIELD_USE_NAMES,
    GEN5_ITEM_POCKET_NAMES,
    NATURAL_GIFT_TYPE_NONE,
    parse_item_record,
)
from romwiki.engines.gen5.shared.learnsets import parse_level_up_learnset
from romwiki.engines.gen5.shared.machines import machine_name, parse_machine_move_table
from romwiki.engines.gen5.shared.map_matrices import parse_map_matrix
from romwiki.engines.gen5.shared.messages import parse_english_message_archive
from romwiki.engines.gen5.shared.moves import parse_move_record
from romwiki.engines.gen5.shared.overworld import (
    is_visible_item_candidate,
    parse_hidden_item_script_table,
    parse_overworld_furniture,
    parse_overworld_npcs,
    parse_overworld_warps,
    parse_visible_item_script_table,
    resolve_hidden_item_id,
    resolve_visible_item_id,
)
from romwiki.engines.gen5.shared.pickup import (
    PICKUP_LEVEL_RANGE_COUNT,
    PICKUP_LEVEL_RANGE_SIZE,
    PICKUP_SLOT_CHANCES,
    PICKUP_TABLE_LOCATOR,
    parse_pickup_table,
    pickup_level_range_item_ids,
)
from romwiki.engines.gen5.shared.script_disassembler import (
    disassemble_function,
    parse_function_offsets,
)
from romwiki.engines.gen5.shared.script_items import find_script_awarded_items
from romwiki.engines.gen5.shared.starter_branches import (
    STARTER_SPECIES_ENTRY_SIZE,
    Gen5StarterBranchFamily,
    parse_starter_branch_families,
    parse_starter_species,
)
from romwiki.engines.gen5.shared.trades import parse_npc_trade_record
from romwiki.engines.gen5.shared.vendors import (
    STANDARD_SHOP_SELECTOR,
    Gen5SpecialVendor,
    parse_shop_dispatch,
)

from .battle_variants import resolve_trainer_variants
from .constants import (
    ENCOUNTER_COSMETIC_FORM_LABELS,
    ENCOUNTER_FORM_SLUGS,
    ITEM_NAME_COUNT,
    PERSONAL_FORM_MEMBERS,
    PERSONAL_INTERNAL_MEMBERS,
    PERSONAL_RECORD_COUNT,
    PERSONAL_TRANSFORMATION_MEMBERS,
    POKEMON_DESCRIPTION_COUNT,
    POKEMON_NAME_COUNT,
    TRAINER_COSMETIC_FORM_LABELS,
    TRAINER_FORM_SLUGS,
)
from .locations import (
    parse_map_header_script_files,
    parse_map_header_table,
    parse_map_header_text_files,
    parse_wild_map_names,
)
from .marts import (
    SHOP_SELECTOR_TO_INVENTORY_ID,
    parse_shop_catalog,
    resolve_special_vendor,
)
from .overworld import (
    resolve_common_script_member,
    resolve_common_script_trainer_id,
)
from .personal import parse_personal_record
from .scripts import (
    find_fossil_revival_script,
    parse_fossil_revival_table,
    parse_trainer_battle_commands,
)
from .static_encounters import discover_static_encounters
from .trainer_party import (
    derive_trainer_party_attributes,
    normalize_trainer_party_member,
)
from .trainers import parse_trainer_record, trainer_name_index

# Move tutors are not a gap to fill in: Ajarmar/universal-pokemon-randomizer-zx's
# Gen5RomHandler.hasMoveTutors() returns true only for Black 2/White 2 --
# tutors were introduced in the sequels and don't exist in this release at all.
#
# Roaming Tornadus/Thundurus species identity is decoded (see
# docs/development/open-items.md) but not yet wired into any dataset here;
# publishing it needs a schema decision, not more binary parsing.
BASE_SPECIES_COUNT = GEN5_BASE_SPECIES_COUNT
INTERNAL_MEMBERS = PERSONAL_INTERNAL_MEMBERS
FORM_MEMBERS = PERSONAL_FORM_MEMBERS
TRANSFORMATION_MEMBERS = PERSONAL_TRANSFORMATION_MEMBERS
MACHINE_COUNT = GEN5_MACHINE_COUNT
MACHINE_TABLE_LOCATOR = GEN5_MACHINE_TABLE_PREFIX
# Consumed generically by pipeline/extraction/items.py (keyed off attribute name, not
# per-engine branching), matching Gen4's own `ITEM_POCKET_NAMES`/
# `ITEM_FIELD_USE_NAMES` precedent.
ITEM_POCKET_NAMES = GEN5_ITEM_POCKET_NAMES
ITEM_FIELD_USE_NAMES = GEN5_ITEM_FIELD_USE_NAMES
ALLOW_DUPLICATE_EGG_MOVES = False
# Unlike Black 2/White 2, no Black/White trade runs through shared trade code
# with separately mapped text, and warp destination IDs are warp indices.
NPC_TRADE_INTERACTION_BY_ID: dict[int, str] = {}
NPC_TRADE_TEXT_MEMBER_BY_ID: dict[int, int] = {}
WARP_DESTINATION_INDEXED = True

__all__ = [
    "NPC_TRADE_INTERACTION_BY_ID",
    "NPC_TRADE_TEXT_MEMBER_BY_ID",
    "WARP_DESTINATION_INDEXED",
    "ALLOW_DUPLICATE_EGG_MOVES",
    "INTERNAL_TO_NATIONAL_DEX",
    "ABILITY_NAME_COUNT",
    "BASE_SPECIES_COUNT",
    "COLOR_NAMES",
    "DAMAGE_CLASS_NAMES",
    "EGG_GROUP_NAMES",
    "ENCOUNTER_COSMETIC_FORM_LABELS",
    "ENCOUNTER_FORM_SLUGS",
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
    "POKEMON_DESCRIPTION_COUNT",
    "POKEMON_NAME_COUNT",
    "TRAINER_COSMETIC_FORM_LABELS",
    "TRAINER_FORM_SLUGS",
    "TRANSFORMATION_MEMBERS",
    "TYPE_NAME_COUNT",
    "TYPE_NAMES",
    "derive_trainer_party_attributes",
    "resolve_trainer_variants",
    "STARTER_SPECIES_ENTRY_SIZE",
    "Gen5StarterBranchFamily",
    "parse_starter_branch_families",
    "parse_starter_species",
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
    "find_script_awarded_items",
    "parse_item_record",
    "parse_level_up_learnset",
    "parse_machine_move_table",
    "parse_map_header_script_files",
    "parse_map_header_text_files",
    "parse_map_header_table",
    "parse_map_matrix",
    "parse_move_record",
    "parse_overworld_furniture",
    "parse_hidden_item_script_table",
    "parse_overworld_npcs",
    "parse_overworld_warps",
    "parse_visible_item_script_table",
    "parse_personal_record",
    "parse_npc_trade_record",
    "parse_pickup_table",
    "parse_shop_catalog",
    "parse_shop_dispatch",
    "resolve_special_vendor",
    "parse_trainer_battle_commands",
    "parse_trainer_record",
    "trainer_name_index",
    "pickup_level_range_item_ids",
    "resolve_hidden_item_id",
    "resolve_visible_item_id",
    "is_visible_item_candidate",
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

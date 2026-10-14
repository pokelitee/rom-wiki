"""Pokémon Black 2 and White 2 engine-specific record support."""

from romwiki.engines.gen5.shared.constants import (
    ABILITY_NAME_COUNT,
    COLOR_NAMES,
    DAMAGE_CLASS_NAMES,
    EGG_GROUP_NAMES,
    EVOLUTION_METHOD_NAMES,
    EVOLUTION_PARAMETER_KINDS,
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
from romwiki.engines.gen5.shared.script_items import find_script_awarded_items
from romwiki.engines.gen5.shared.starter_branches import (
    STARTER_SPECIES_ENTRY_SIZE,
    parse_starter_branch_families,
    parse_starter_species,
)
from romwiki.engines.gen5.shared.trades import parse_npc_trade_record
from romwiki.engines.gen5.shared.vendors import (
    STANDARD_SHOP_SELECTOR,
    parse_shop_dispatch,
)

from .battle_variants import resolve_trainer_variants
from .constants import (
    ENCOUNTER_COSMETIC_FORM_LABELS,
    ENCOUNTER_FORM_SLUGS,
    GEN5_BASE_SPECIES_COUNT,
    GEN5_ITEM_FIELD_USE_NAMES,
    GEN5_MACHINE_COUNT,
    ITEM_NAME_COUNT,
    PERSONAL_FORM_MEMBERS,
    PERSONAL_INTERNAL_MEMBERS,
    PERSONAL_RECORD_COUNT,
    PERSONAL_RECORD_SIZE,
    PERSONAL_TRANSFORMATION_MEMBERS,
    POKEMON_DESCRIPTION_COUNT,
    POKEMON_NAME_COUNT,
    TRAINER_COSMETIC_FORM_LABELS,
    TRAINER_FORM_SLUGS,
)
from .difficulty_branches import parse_difficulty_branch_families
from .disassembler import disassemble_function, parse_function_offsets
from .hidden_grottos import (
    HIDDEN_GROTTO_RECORD_SIZE,
    hidden_grotto_id_for_dispatch,
    parse_hidden_grotto_record,
)
from .locations import (
    COMMON_SCRIPT_MEMBER_BASE,
    NPC_TRADE_INTERACTION_BY_ID,
    NPC_TRADE_TEXT_MEMBER_BY_ID,
    WARP_DESTINATION_INDEXED,
    parse_map_header_script_files,
    parse_map_header_table,
    parse_map_header_text_files,
    parse_wild_map_names,
    resolve_common_script_member,
)
from .marts import (
    SHOP_SELECTOR_TO_INVENTORY_ID,
    parse_archive_shop_catalog,
    resolve_location_special_vendors,
    resolve_special_vendor,
)
from .personal import parse_personal_record
from .static_encounters import discover_static_encounters, find_fossil_revival_script
from .swarms import SWARM_RECORD_SIZE, SwarmEncounter, parse_swarm_table
from .trainer_party import (
    derive_trainer_party_attributes,
    normalize_trainer_party_member,
)
from .trainers import (
    CHECK_TRAINER_BATTLE_WON,
    START_TRAINER_BATTLE,
    parse_overworld_npcs,
    parse_trainer_battle_commands,
    parse_trainer_record,
    resolve_common_script_trainer_id,
    trainer_name_index,
)
from .tutors import (
    TUTOR_COMPATIBILITY_OFFSET,
    TUTOR_COUNT,
    TUTOR_LOCATION_NAMES,
    TUTOR_RECORD_SIZE,
    parse_tutor_compatibility_record,
    parse_tutor_move_table,
)

BASE_SPECIES_COUNT = GEN5_BASE_SPECIES_COUNT
INTERNAL_MEMBERS = PERSONAL_INTERNAL_MEMBERS
FORM_MEMBERS = PERSONAL_FORM_MEMBERS
TRANSFORMATION_MEMBERS = PERSONAL_TRANSFORMATION_MEMBERS
MACHINE_COUNT = GEN5_MACHINE_COUNT
ITEM_FIELD_USE_NAMES = GEN5_ITEM_FIELD_USE_NAMES
ALLOW_DUPLICATE_EGG_MOVES = False
ITEM_POCKET_NAMES = GEN5_ITEM_POCKET_NAMES
MACHINE_TABLE_LOCATOR = GEN5_MACHINE_TABLE_PREFIX

__all__ = [
    "ALLOW_DUPLICATE_EGG_MOVES",
    "INTERNAL_TO_NATIONAL_DEX",
    "ABILITY_NAME_COUNT",
    "COLOR_NAMES",
    "DAMAGE_CLASS_NAMES",
    "EGG_GROUP_NAMES",
    "ENCOUNTER_METHOD_NAMES",
    "ENCOUNTER_METHOD_SLOT_CHANCES",
    "EVOLUTION_METHOD_NAMES",
    "EVOLUTION_PARAMETER_KINDS",
    "GROWTH_RATE_NAMES",
    "ITEM_POCKET_NAMES",
    "MACHINE_TABLE_LOCATOR",
    "MAX_MOVE_ID",
    "MOVE_NAME_COUNT",
    "MOVE_RECORD_COUNT",
    "NATURAL_GIFT_TYPE_NONE",
    "PICKUP_LEVEL_RANGE_COUNT",
    "PICKUP_LEVEL_RANGE_SIZE",
    "PICKUP_SLOT_CHANCES",
    "PICKUP_TABLE_LOCATOR",
    "STANDARD_SHOP_SELECTOR",
    "STARTER_SPECIES_ENTRY_SIZE",
    "TYPE_NAME_COUNT",
    "TYPE_NAMES",
    "is_visible_item_candidate",
    "machine_name",
    "parse_egg_move_set",
    "parse_encounter_entry",
    "parse_english_message_archive",
    "parse_evolution_record",
    "parse_hidden_item_script_table",
    "parse_item_record",
    "parse_level_up_learnset",
    "parse_machine_move_table",
    "parse_map_matrix",
    "parse_move_record",
    "parse_npc_trade_record",
    "parse_overworld_furniture",
    "parse_overworld_warps",
    "parse_pickup_table",
    "parse_shop_dispatch",
    "parse_starter_branch_families",
    "parse_starter_species",
    "parse_visible_item_script_table",
    "pickup_level_range_item_ids",
    "resolve_hidden_item_id",
    "resolve_visible_item_id",
    "BASE_SPECIES_COUNT",
    "CHECK_TRAINER_BATTLE_WON",
    "COMMON_SCRIPT_MEMBER_BASE",
    "ENCOUNTER_COSMETIC_FORM_LABELS",
    "ENCOUNTER_FORM_SLUGS",
    "FORM_MEMBERS",
    "HIDDEN_GROTTO_RECORD_SIZE",
    "GEN5_BASE_SPECIES_COUNT",
    "GEN5_ITEM_FIELD_USE_NAMES",
    "GEN5_MACHINE_COUNT",
    "INTERNAL_MEMBERS",
    "ITEM_FIELD_USE_NAMES",
    "ITEM_NAME_COUNT",
    "MACHINE_COUNT",
    "NPC_TRADE_INTERACTION_BY_ID",
    "NPC_TRADE_TEXT_MEMBER_BY_ID",
    "PERSONAL_FORM_MEMBERS",
    "PERSONAL_INTERNAL_MEMBERS",
    "PERSONAL_RECORD_COUNT",
    "PERSONAL_RECORD_SIZE",
    "PERSONAL_TRANSFORMATION_MEMBERS",
    "POKEMON_DESCRIPTION_COUNT",
    "POKEMON_NAME_COUNT",
    "SWARM_RECORD_SIZE",
    "SwarmEncounter",
    "SHOP_SELECTOR_TO_INVENTORY_ID",
    "START_TRAINER_BATTLE",
    "TUTOR_COMPATIBILITY_OFFSET",
    "TUTOR_COUNT",
    "TUTOR_LOCATION_NAMES",
    "TUTOR_RECORD_SIZE",
    "TRAINER_COSMETIC_FORM_LABELS",
    "TRAINER_FORM_SLUGS",
    "TRANSFORMATION_MEMBERS",
    "WARP_DESTINATION_INDEXED",
    "discover_static_encounters",
    "derive_trainer_party_attributes",
    "resolve_trainer_variants",
    "find_fossil_revival_script",
    "find_script_awarded_items",
    "hidden_grotto_id_for_dispatch",
    "disassemble_function",
    "parse_personal_record",
    "parse_hidden_grotto_record",
    "parse_map_header_script_files",
    "parse_map_header_text_files",
    "parse_map_header_table",
    "parse_overworld_npcs",
    "parse_function_offsets",
    "parse_archive_shop_catalog",
    "parse_difficulty_branch_families",
    "parse_tutor_compatibility_record",
    "parse_tutor_move_table",
    "parse_trainer_battle_commands",
    "parse_trainer_record",
    "parse_wild_map_names",
    "resolve_common_script_member",
    "resolve_common_script_trainer_id",
    "trainer_name_index",
    "resolve_location_special_vendors",
    "resolve_special_vendor",
    "parse_swarm_table",
    "normalize_trainer_party_member",
]

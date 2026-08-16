"""Pokémon Black 2 and White 2 engine-specific record support."""

from romwiki.engines.gen5.script_items import find_script_awarded_items

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

__all__ = [
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

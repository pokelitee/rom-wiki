from romwiki.engines.gen4_dppt.berries import (
    GEN4_BERRY_FIRMNESS_NAMES,
    Gen4BerryData,
    parse_berry_record,
)
from romwiki.engines.gen4_dppt.bonus_encounters import (
    GEN4_GREAT_MARSH_POST_NATIONAL_DEX_MEMBER,
    GEN4_GREAT_MARSH_PRE_NATIONAL_DEX_MEMBER,
    GEN4_HONEY_TREE_COMMON_MEMBER,
    GEN4_HONEY_TREE_GROUP_CHANCES,
    GEN4_HONEY_TREE_MUNCHLAX_GROUP_CHANCES,
    GEN4_HONEY_TREE_RARE_MEMBER,
    GEN4_HONEY_TREE_UNCOMMON_MEMBER,
    GEN4_TROPHY_GARDEN_MEMBER,
    parse_species_list,
)
from romwiki.engines.gen4_dppt.constants import (
    ABILITY_NAME_COUNT,
    COLOR_NAMES,
    DAMAGE_CLASS_NAMES,
    EGG_GROUP_NAMES,
    EVOLUTION_METHOD_NAMES,
    EVOLUTION_PARAMETER_KINDS,
    GEN4_ARCHIVE_MEMBER_NONE,
    GEN4_MAX_FRIENDSHIP,
    GROWTH_RATE_NAMES,
    ITEM_NAME_COUNT,
    MAX_MOVE_ID,
    MOVE_NAME_COUNT,
    MOVE_RECORD_COUNT,
    NATURAL_GIFT_TYPE_NONE,
    PERSONAL_RECORD_COUNT,
    PLATINUM_DYNAMIC_WARP_HEADER_ID,
    PLATINUM_DYNAMIC_WARP_ID,
    PLATINUM_GAME_CORNER_PRIZE_EXCHANGE_HEADER_ID,
    PLATINUM_GREAT_MARSH_HEADER_IDS,
    PLATINUM_HONEY_TREE_HEADER_IDS,
    PLATINUM_MATRIX_VOID_HEADER_IDS,
    PLATINUM_ROAMING_SLOT_SPECIES_IDS,
    PLATINUM_TROPHY_GARDEN_HEADER_ID,
    POKEMON_NAME_COUNT,
    TYPE_NAME_COUNT,
    TYPE_NAMES,
)
from romwiki.engines.gen4_dppt.egg_moves import (
    EGG_MOVE_SPECIES_MARKER_BASE,
    EGG_MOVE_TABLE_TERMINATOR,
    parse_egg_move_table,
)
from romwiki.engines.gen4_dppt.encounters import (
    DUAL_SLOT_GAMES,
    ENCOUNTER_RECORD_SIZES,
    GEN4_DUAL_SLOT_SLOT_INDICES,
    GEN4_FISHING_SLOT_CHANCES,
    GEN4_RADAR_SLOT_INDICES,
    GEN4_SWARM_SLOT_INDICES,
    GEN4_TIMED_SLOT_INDICES,
    GEN4_UNOWN_FORM_NAMES,
    GEN4_UNOWN_FORM_TABLES,
    GEN4_WALKING_SLOT_CHANCES,
    GEN4_WATER_SLOT_CHANCES,
    parse_encounter_record,
)
from romwiki.engines.gen4_dppt.events import (
    Gen4BackgroundEvent,
    Gen4MapEvents,
    Gen4ObjectEvent,
    Gen4WarpEvent,
    parse_map_events,
    parse_object_events,
    parse_warp_events,
)
from romwiki.engines.gen4_dppt.evolutions import (
    EVOLUTION_RECORD_SIZE,
    EVOLUTION_SLOT_COUNT,
    EVOLUTION_SLOT_SIZE,
    parse_evolution_record,
)
from romwiki.engines.gen4_dppt.fossils import (
    Gen4FossilRevival,
    parse_fossil_revival_table,
)
from romwiki.engines.gen4_dppt.game_corner import (
    Gen4GameCornerPrize,
    parse_game_corner_prizes,
)
from romwiki.engines.gen4_dppt.gifts import (
    GIVE_EGG_COMMAND,
    GIVE_POKEMON_COMMAND,
    Gen4EggGiftCommand,
    Gen4PokemonGiftCommand,
    parse_egg_gift_command,
    parse_pokemon_gift_commands,
)
from romwiki.engines.gen4_dppt.items import (
    GEN4_ITEM_ARCHIVE_MAP_RECORD_SIZE,
    GEN4_ITEM_FIELD_USE_NAMES,
    GEN4_ITEM_POCKET_NAMES,
    GEN4_ITEM_RECORD_SIZE,
    find_item_archive_members,
    parse_item_record,
)
from romwiki.engines.gen4_dppt.learnsets import (
    LEARNSET_TERMINATOR,
    LEVEL_SHIFT,
    MOVE_ID_MASK,
    parse_level_up_learnset,
)
from romwiki.engines.gen4_dppt.machines import (
    GEN4_MACHINE_COUNT,
    GEN4_TM_COUNT,
    machine_name,
    parse_machine_move_table,
)
from romwiki.engines.gen4_dppt.map_headers import (
    MAP_HEADER_SIZE,
    PlatinumMapHeader,
    parse_platinum_map_headers,
)
from romwiki.engines.gen4_dppt.map_matrices import Gen4MapMatrix, parse_map_matrix
from romwiki.engines.gen4_dppt.marts import (
    COMMON_MART_COMMAND,
    DECORATION_MART_COMMAND,
    DECORATION_RECORD_SIZE,
    FRONTIER_MART_COMMAND,
    ITEM_RECORD_SIZE,
    SEAL_MART_COMMAND,
    SEAL_RECORD_SIZE,
    SPECIALTY_MART_COMMAND,
    Gen4CommonMartItem,
    Gen4MartCommand,
    parse_common_mart_inventory,
    parse_decoration_price_table,
    parse_frontier_price_table,
    parse_item_price,
    parse_mart_commands,
    parse_seal_price_table,
    parse_specialty_mart_inventories,
)
from romwiki.engines.gen4_dppt.messages import parse_english_message_archive
from romwiki.engines.gen4_dppt.moves import MOVE_RECORD_SIZE, parse_move_record
from romwiki.engines.gen4_dppt.personal import (
    GEN4_BASE_SPECIES_COUNT,
    PERSONAL_FORM_MEMBERS,
    PERSONAL_INTERNAL_MEMBERS,
    PERSONAL_RECORD_SIZE,
    TRAINER_COSMETIC_FORM_LABELS,
    TRAINER_FORM_SLUGS,
    parse_personal_record,
)
from romwiki.engines.gen4_dppt.pickup import Gen4PickupTables, parse_pickup_tables
from romwiki.engines.gen4_dppt.scripts import (
    CHECK_WON_BATTLE,
    PLATINUM_ROAMING_SLOT_COUNT,
    START_TRAINER_BATTLE,
    Gen4RoamingActivationCommand,
    Gen4StaticEncounterCommand,
    Gen4TrainerBattleCommand,
    parse_roaming_activation_commands,
    parse_script_table,
    parse_static_encounter_commands,
    parse_trainer_battle_commands,
)
from romwiki.engines.gen4_dppt.trades import (
    NPC_TRADE_RECORD_SIZE,
    Gen4NpcTrade,
    Gen4NpcTradeCommand,
    parse_npc_trade_commands,
    parse_npc_trade_record,
)
from romwiki.engines.gen4_dppt.trainer_party import (
    derive_trainer_party_attributes,
    normalize_trainer_party_member,
)
from romwiki.engines.gen4_dppt.trainers import (
    TRAINER_RECORD_SIZE,
    parse_trainer_class_genders,
    parse_trainer_record,
)
from romwiki.engines.gen4_dppt.tutors import (
    TUTOR_COMPATIBILITY_RECORD_SIZE,
    TUTOR_RECORD_SIZE,
    parse_special_tutor_move,
    parse_special_tutor_species,
    parse_tutor_compatibility_table,
    parse_tutor_move_table,
)

# Engine-neutral adapter contract. The pipeline accesses every engine
# through these names via `romwiki.engines.registry`; the gen4/Platinum-
# prefixed originals above remain for engine-internal use and tests.
ARCHIVE_MEMBER_NONE = GEN4_ARCHIVE_MEMBER_NONE
MAX_FRIENDSHIP = GEN4_MAX_FRIENDSHIP
DYNAMIC_WARP_HEADER_ID = PLATINUM_DYNAMIC_WARP_HEADER_ID
DYNAMIC_WARP_ID = PLATINUM_DYNAMIC_WARP_ID
MATRIX_VOID_HEADER_IDS = PLATINUM_MATRIX_VOID_HEADER_IDS
ROAMING_SLOT_COUNT = PLATINUM_ROAMING_SLOT_COUNT
BASE_SPECIES_COUNT = GEN4_BASE_SPECIES_COUNT
MACHINE_COUNT = GEN4_MACHINE_COUNT
INTERNAL_MEMBERS = PERSONAL_INTERNAL_MEMBERS
FORM_MEMBERS = PERSONAL_FORM_MEMBERS
WALKING_SLOT_CHANCES = GEN4_WALKING_SLOT_CHANCES
WATER_SLOT_CHANCES = GEN4_WATER_SLOT_CHANCES
FISHING_SLOT_CHANCES = GEN4_FISHING_SLOT_CHANCES
SWARM_SLOT_INDICES = GEN4_SWARM_SLOT_INDICES
TIMED_SLOT_INDICES = GEN4_TIMED_SLOT_INDICES
DUAL_SLOT_SLOT_INDICES = GEN4_DUAL_SLOT_SLOT_INDICES
RADAR_SLOT_INDICES = GEN4_RADAR_SLOT_INDICES
UNOWN_FORM_NAMES = GEN4_UNOWN_FORM_NAMES
UNOWN_FORM_TABLES = GEN4_UNOWN_FORM_TABLES
ITEM_POCKET_NAMES = GEN4_ITEM_POCKET_NAMES
ITEM_FIELD_USE_NAMES = GEN4_ITEM_FIELD_USE_NAMES
parse_map_headers = parse_platinum_map_headers
HONEY_TREE_HEADER_IDS = PLATINUM_HONEY_TREE_HEADER_IDS
GREAT_MARSH_HEADER_IDS = PLATINUM_GREAT_MARSH_HEADER_IDS
TROPHY_GARDEN_HEADER_ID = PLATINUM_TROPHY_GARDEN_HEADER_ID
HONEY_TREE_GROUP_CHANCES = GEN4_HONEY_TREE_GROUP_CHANCES
HONEY_TREE_MUNCHLAX_GROUP_CHANCES = GEN4_HONEY_TREE_MUNCHLAX_GROUP_CHANCES
ROAMING_SLOT_SPECIES_IDS = PLATINUM_ROAMING_SLOT_SPECIES_IDS
GAME_CORNER_PRIZE_EXCHANGE_HEADER_ID = PLATINUM_GAME_CORNER_PRIZE_EXCHANGE_HEADER_ID
BERRY_FIRMNESS_NAMES = GEN4_BERRY_FIRMNESS_NAMES

__all__ = [
    "ABILITY_NAME_COUNT",
    "ARCHIVE_MEMBER_NONE",
    "BASE_SPECIES_COUNT",
    "CHECK_WON_BATTLE",
    "COLOR_NAMES",
    "DAMAGE_CLASS_NAMES",
    "DYNAMIC_WARP_HEADER_ID",
    "DYNAMIC_WARP_ID",
    "EGG_GROUP_NAMES",
    "EVOLUTION_METHOD_NAMES",
    "EVOLUTION_PARAMETER_KINDS",
    "FISHING_SLOT_CHANCES",
    "FORM_MEMBERS",
    "GROWTH_RATE_NAMES",
    "INTERNAL_MEMBERS",
    "ITEM_FIELD_USE_NAMES",
    "ITEM_NAME_COUNT",
    "ITEM_POCKET_NAMES",
    "MACHINE_COUNT",
    "MATRIX_VOID_HEADER_IDS",
    "MAX_FRIENDSHIP",
    "MAX_MOVE_ID",
    "MOVE_NAME_COUNT",
    "MOVE_RECORD_COUNT",
    "NATURAL_GIFT_TYPE_NONE",
    "PERSONAL_RECORD_COUNT",
    "POKEMON_NAME_COUNT",
    "ROAMING_SLOT_COUNT",
    "START_TRAINER_BATTLE",
    "TRAINER_COSMETIC_FORM_LABELS",
    "TRAINER_FORM_SLUGS",
    "TYPE_NAME_COUNT",
    "TYPE_NAMES",
    "DUAL_SLOT_SLOT_INDICES",
    "RADAR_SLOT_INDICES",
    "SWARM_SLOT_INDICES",
    "TIMED_SLOT_INDICES",
    "UNOWN_FORM_NAMES",
    "UNOWN_FORM_TABLES",
    "WALKING_SLOT_CHANCES",
    "WATER_SLOT_CHANCES",
    "machine_name",
    "parse_map_headers",
    "GEN4_ARCHIVE_MEMBER_NONE",
    "GEN4_BASE_SPECIES_COUNT",
    "GEN4_MAX_FRIENDSHIP",
    "PLATINUM_DYNAMIC_WARP_HEADER_ID",
    "PLATINUM_DYNAMIC_WARP_ID",
    "PLATINUM_MATRIX_VOID_HEADER_IDS",
    "PLATINUM_HONEY_TREE_HEADER_IDS",
    "PLATINUM_GREAT_MARSH_HEADER_IDS",
    "PLATINUM_TROPHY_GARDEN_HEADER_ID",
    "PLATINUM_ROAMING_SLOT_SPECIES_IDS",
    "ROAMING_SLOT_SPECIES_IDS",
    "PLATINUM_GAME_CORNER_PRIZE_EXCHANGE_HEADER_ID",
    "GAME_CORNER_PRIZE_EXCHANGE_HEADER_ID",
    "Gen4GameCornerPrize",
    "parse_game_corner_prizes",
    "Gen4PickupTables",
    "parse_pickup_tables",
    "Gen4FossilRevival",
    "parse_fossil_revival_table",
    "GEN4_BERRY_FIRMNESS_NAMES",
    "BERRY_FIRMNESS_NAMES",
    "Gen4BerryData",
    "parse_berry_record",
    "HONEY_TREE_HEADER_IDS",
    "GREAT_MARSH_HEADER_IDS",
    "TROPHY_GARDEN_HEADER_ID",
    "HONEY_TREE_GROUP_CHANCES",
    "HONEY_TREE_MUNCHLAX_GROUP_CHANCES",
    "GEN4_HONEY_TREE_COMMON_MEMBER",
    "GEN4_HONEY_TREE_UNCOMMON_MEMBER",
    "GEN4_HONEY_TREE_RARE_MEMBER",
    "GEN4_TROPHY_GARDEN_MEMBER",
    "GEN4_GREAT_MARSH_POST_NATIONAL_DEX_MEMBER",
    "GEN4_GREAT_MARSH_PRE_NATIONAL_DEX_MEMBER",
    "GEN4_HONEY_TREE_GROUP_CHANCES",
    "GEN4_HONEY_TREE_MUNCHLAX_GROUP_CHANCES",
    "parse_species_list",
    "PERSONAL_FORM_MEMBERS",
    "PERSONAL_INTERNAL_MEMBERS",
    "PERSONAL_RECORD_SIZE",
    "parse_personal_record",
    "DUAL_SLOT_GAMES",
    "ENCOUNTER_RECORD_SIZES",
    "GEN4_DUAL_SLOT_SLOT_INDICES",
    "GEN4_FISHING_SLOT_CHANCES",
    "GEN4_RADAR_SLOT_INDICES",
    "GEN4_SWARM_SLOT_INDICES",
    "GEN4_TIMED_SLOT_INDICES",
    "GEN4_UNOWN_FORM_NAMES",
    "GEN4_UNOWN_FORM_TABLES",
    "GEN4_WALKING_SLOT_CHANCES",
    "GEN4_WATER_SLOT_CHANCES",
    "parse_encounter_record",
    "MAP_HEADER_SIZE",
    "PlatinumMapHeader",
    "parse_english_message_archive",
    "GEN4_ITEM_ARCHIVE_MAP_RECORD_SIZE",
    "GEN4_ITEM_FIELD_USE_NAMES",
    "GEN4_ITEM_POCKET_NAMES",
    "GEN4_ITEM_RECORD_SIZE",
    "find_item_archive_members",
    "parse_item_record",
    "parse_platinum_map_headers",
    "Gen4MapMatrix",
    "parse_map_matrix",
    "TRAINER_RECORD_SIZE",
    "parse_trainer_class_genders",
    "parse_trainer_record",
    "Gen4ObjectEvent",
    "Gen4BackgroundEvent",
    "Gen4MapEvents",
    "Gen4WarpEvent",
    "parse_map_events",
    "parse_object_events",
    "parse_warp_events",
    "Gen4TrainerBattleCommand",
    "Gen4RoamingActivationCommand",
    "Gen4StaticEncounterCommand",
    "PLATINUM_ROAMING_SLOT_COUNT",
    "parse_roaming_activation_commands",
    "parse_script_table",
    "parse_static_encounter_commands",
    "parse_trainer_battle_commands",
    "MOVE_RECORD_SIZE",
    "parse_move_record",
    "LEARNSET_TERMINATOR",
    "LEVEL_SHIFT",
    "MOVE_ID_MASK",
    "parse_level_up_learnset",
    "EGG_MOVE_SPECIES_MARKER_BASE",
    "EGG_MOVE_TABLE_TERMINATOR",
    "parse_egg_move_table",
    "EVOLUTION_RECORD_SIZE",
    "EVOLUTION_SLOT_COUNT",
    "EVOLUTION_SLOT_SIZE",
    "parse_evolution_record",
    "GIVE_EGG_COMMAND",
    "GIVE_POKEMON_COMMAND",
    "Gen4EggGiftCommand",
    "Gen4PokemonGiftCommand",
    "parse_egg_gift_command",
    "parse_pokemon_gift_commands",
    "GEN4_MACHINE_COUNT",
    "GEN4_TM_COUNT",
    "parse_machine_move_table",
    "COMMON_MART_COMMAND",
    "DECORATION_RECORD_SIZE",
    "DECORATION_MART_COMMAND",
    "FRONTIER_MART_COMMAND",
    "ITEM_RECORD_SIZE",
    "SEAL_MART_COMMAND",
    "SEAL_RECORD_SIZE",
    "SPECIALTY_MART_COMMAND",
    "Gen4CommonMartItem",
    "Gen4MartCommand",
    "parse_common_mart_inventory",
    "parse_decoration_price_table",
    "parse_frontier_price_table",
    "parse_item_price",
    "parse_mart_commands",
    "parse_seal_price_table",
    "parse_specialty_mart_inventories",
    "TUTOR_COMPATIBILITY_RECORD_SIZE",
    "TUTOR_RECORD_SIZE",
    "parse_tutor_compatibility_table",
    "parse_tutor_move_table",
    "parse_special_tutor_move",
    "parse_special_tutor_species",
    "NPC_TRADE_RECORD_SIZE",
    "Gen4NpcTrade",
    "Gen4NpcTradeCommand",
    "parse_npc_trade_commands",
    "parse_npc_trade_record",
    "derive_trainer_party_attributes",
    "normalize_trainer_party_member",
]

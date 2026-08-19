from romwiki.engines.gen4.constants import (
    ABILITY_NAME_COUNT,
    COLOR_NAMES,
    DAMAGE_CLASS_NAMES,
    EGG_GROUP_NAMES,
    EVOLUTION_METHOD_NAMES,
    EVOLUTION_PARAMETER_KINDS,
    GEN4_MAX_FRIENDSHIP,
    GROWTH_RATE_NAMES,
    MAX_MOVE_ID,
    MOVE_NAME_COUNT,
    MOVE_RECORD_COUNT,
    NATURAL_GIFT_TYPE_NONE,
    PERSONAL_RECORD_COUNT,
    POKEMON_NAME_COUNT,
    TYPE_NAME_COUNT,
    TYPE_NAMES,
)
from romwiki.engines.gen4.egg_moves import parse_egg_move_table
from romwiki.engines.gen4.events import (
    is_trainer_object_candidate,
    parse_map_events,
    parse_object_events,
)
from romwiki.engines.gen4.evolutions import parse_evolution_record
from romwiki.engines.gen4.items import (
    GEN4_ITEM_FIELD_USE_NAMES,
    GEN4_ITEM_POCKET_NAMES,
    find_item_archive_members,
    parse_item_record,
)
from romwiki.engines.gen4.learnsets import parse_level_up_learnset
from romwiki.engines.gen4.machines import (
    GEN4_MACHINE_COUNT,
    GEN4_TM_COUNT,
    machine_name,
    parse_machine_move_table,
)
from romwiki.engines.gen4.map_matrices import parse_map_matrix
from romwiki.engines.gen4.messages import parse_english_message_archive
from romwiki.engines.gen4.moves import MOVE_RECORD_SIZE, parse_move_record
from romwiki.engines.gen4.personal import (
    GEN4_BASE_SPECIES_COUNT,
    PERSONAL_FORM_MEMBERS,
    PERSONAL_INTERNAL_MEMBERS,
    PERSONAL_RECORD_SIZE,
    TRAINER_COSMETIC_FORM_LABELS,
    parse_personal_record,
)
from romwiki.engines.gen4.personal import (
    TRAINER_FORM_SLUGS as GEN4_TRAINER_FORM_SLUGS,
)
from romwiki.engines.gen4.starter_branches import (
    GET_STARTER_SPECIES as GET_STARTER_SPECIES,
)
from romwiki.engines.gen4.starter_branches import (
    Gen4StarterBranchFamily as Gen4StarterBranchFamily,
)
from romwiki.engines.gen4.starter_branches import (
    parse_starter_branch_families as _parse_starter_branch_families,
)
from romwiki.engines.gen4.starter_species import (
    STARTER_SPECIES_ENTRY_SIZE,
    parse_starter_species,
)
from romwiki.engines.gen4.trainer_party import (
    derive_trainer_party_attributes,
    normalize_trainer_party_member,
)
from romwiki.engines.gen4.trainers import (
    parse_trainer_class_genders,
    parse_trainer_class_prize_multipliers,
    parse_trainer_record,
)

from .battle_variants import resolve_trainer_variants
from .encounters import (
    HGSS_FISHING_SLOT_CHANCES,
    HGSS_ROCK_SMASH_SLOT_CHANCES,
    HGSS_WALKING_SLOT_CHANCES,
    HGSS_WATER_SLOT_CHANCES,
    parse_encounter_record,
)
from .events import (
    ITEM_BALL_TABLE_SCRIPT_MEMBER,
    is_hidden_item_candidate,
    is_visible_item_candidate,
    parse_hidden_item_table,
    parse_item_ball_table,
    resolve_hidden_item_id,
    resolve_visible_item_id,
)
from .gifts import Gen4HgssPokemonGiftCommand, parse_pokemon_gift_commands
from .headbutt import HEADBUTT_SLOT_CHANCES, parse_headbutt_record
from .map_headers import MAP_HEADER_SIZE, parse_map_headers
from .marts import Gen4HgssMartDispatchCommand, parse_mart_dispatch_commands, parse_shop_catalog
from .pickup import (
    PICKUP_COMMON_ITEM_COUNT,
    PICKUP_COMMON_TABLE_LOCATOR,
    PICKUP_LEVEL_RANGE_COUNT,
    PICKUP_LEVEL_RANGE_SIZE,
    PICKUP_RARE_ITEM_COUNT,
    PICKUP_RARE_TABLE_LOCATOR,
    PICKUP_SLOT_CHANCES,
    parse_pickup_item_table,
    pickup_level_range_item_ids,
)
from .safari import SAFARI_AREA_NAMES, parse_safari_encounter_record
from .script_items import find_script_awarded_items
from .scripts import (
    CHECK_WON_BATTLE,
    START_TRAINER_BATTLE,
    START_WILD_BATTLE,
    Gen4StaticEncounterCommand,
    Gen4TrainerBattleCommand,
    parse_static_encounter_commands,
    parse_trainer_battle_commands,
)
from .trades import NPC_TRADE_RECORD_SIZE, parse_npc_trade_record
from .tutors import (
    TUTOR_COMPATIBILITY_RECORD_SIZE,
    TUTOR_COUNT,
    TUTOR_LOCATION_NAMES,
    TUTOR_RECORD_SIZE,
    parse_tutor_compatibility_table,
    parse_tutor_move_table,
)

parse_map_header_table = parse_map_headers

BASE_SPECIES_COUNT = GEN4_BASE_SPECIES_COUNT
FORM_MEMBERS = PERSONAL_FORM_MEMBERS
INTERNAL_MEMBERS = PERSONAL_INTERNAL_MEMBERS
MACHINE_COUNT = GEN4_MACHINE_COUNT
MAX_FRIENDSHIP = GEN4_MAX_FRIENDSHIP
ITEM_NAME_COUNT = 537
ITEM_POCKET_NAMES = GEN4_ITEM_POCKET_NAMES
ITEM_FIELD_USE_NAMES = GEN4_ITEM_FIELD_USE_NAMES + (
    "unown-report",
    "dowsing-machine",
    "gb-sounds",
    "gracidea",
    "vs-recorder",
)
MACHINE_TABLE_LOCATOR = "1E003200"
CODE_BINARY_DECOMPRESSED = True
ARCHIVE_MEMBER_NONE = 0
ENCOUNTER_MEMBER_NONE = 0xFF
MATRIX_VOID_HEADER_IDS = frozenset((0, 0xFFFF))
DYNAMIC_WARP_HEADER_ID = 0xFFF
DYNAMIC_WARP_ID = 0x100
WALKING_SLOT_CHANCES = HGSS_WALKING_SLOT_CHANCES
WATER_SLOT_CHANCES = HGSS_WATER_SLOT_CHANCES
FISHING_SLOT_CHANCES = HGSS_FISHING_SLOT_CHANCES
ROCK_SMASH_SLOT_CHANCES = HGSS_ROCK_SMASH_SLOT_CHANCES
FIRST_TRAINER_ID = 1
TRAINER_LOCATION_EXTRACTION = True
TRAINER_SCRIPT_REFERENCE_EXTRACTION = True
TRAINER_OBJECT_SCRIPT_START = 3000
TRAINER_OBJECT_SCRIPT_END = 3999
TRAINER_OBJECT_ID_OFFSET = 1
ALLOW_DUPLICATE_EGG_MOVES = True
# Sacred Gold and Storm Silver v1.05 both store form bits 1 on trainer 229's
# Pinsir. Pinsir has no Generation IV form, so retain the raw form ID while
# resolving its display/reference target to the base species.
TRAINER_FORM_SLUGS = {**GEN4_TRAINER_FORM_SLUGS, (127, 1): "pinsir"}

__all__ = [
    "ABILITY_NAME_COUNT",
    "BASE_SPECIES_COUNT",
    "CHECK_WON_BATTLE",
    "COLOR_NAMES",
    "DAMAGE_CLASS_NAMES",
    "EGG_GROUP_NAMES",
    "FORM_MEMBERS",
    "GROWTH_RATE_NAMES",
    "HEADBUTT_SLOT_CHANCES",
    "INTERNAL_MEMBERS",
    "ITEM_NAME_COUNT",
    "MACHINE_COUNT",
    "MAX_FRIENDSHIP",
    "MAX_MOVE_ID",
    "MOVE_NAME_COUNT",
    "MOVE_RECORD_COUNT",
    "MOVE_RECORD_SIZE",
    "NATURAL_GIFT_TYPE_NONE",
    "NPC_TRADE_RECORD_SIZE",
    "PERSONAL_FORM_MEMBERS",
    "PERSONAL_INTERNAL_MEMBERS",
    "PERSONAL_RECORD_COUNT",
    "PERSONAL_RECORD_SIZE",
    "PICKUP_COMMON_ITEM_COUNT",
    "PICKUP_COMMON_TABLE_LOCATOR",
    "PICKUP_LEVEL_RANGE_COUNT",
    "PICKUP_LEVEL_RANGE_SIZE",
    "PICKUP_RARE_ITEM_COUNT",
    "PICKUP_RARE_TABLE_LOCATOR",
    "PICKUP_SLOT_CHANCES",
    "POKEMON_NAME_COUNT",
    "TYPE_NAME_COUNT",
    "TYPE_NAMES",
    "TUTOR_COMPATIBILITY_RECORD_SIZE",
    "TUTOR_COUNT",
    "TUTOR_LOCATION_NAMES",
    "TUTOR_RECORD_SIZE",
    "TRAINER_COSMETIC_FORM_LABELS",
    "TRAINER_FORM_SLUGS",
    "EVOLUTION_METHOD_NAMES",
    "EVOLUTION_PARAMETER_KINDS",
    "ITEM_FIELD_USE_NAMES",
    "ITEM_POCKET_NAMES",
    "MACHINE_TABLE_LOCATOR",
    "GEN4_TM_COUNT",
    "MAP_HEADER_SIZE",
    "SAFARI_AREA_NAMES",
    "START_TRAINER_BATTLE",
    "START_WILD_BATTLE",
    "Gen4TrainerBattleCommand",
    "Gen4StaticEncounterCommand",
    "Gen4HgssPokemonGiftCommand",
    "Gen4HgssMartDispatchCommand",
    "parse_egg_move_table",
    "parse_encounter_record",
    "parse_headbutt_record",
    "parse_safari_encounter_record",
    "parse_evolution_record",
    "parse_item_record",
    "find_item_archive_members",
    "parse_level_up_learnset",
    "parse_machine_move_table",
    "parse_map_headers",
    "parse_map_header_table",
    "parse_map_matrix",
    "parse_shop_catalog",
    "parse_map_events",
    "parse_object_events",
    "resolve_hidden_item_id",
    "resolve_visible_item_id",
    "is_hidden_item_candidate",
    "is_visible_item_candidate",
    "is_trainer_object_candidate",
    "ITEM_BALL_TABLE_SCRIPT_MEMBER",
    "parse_item_ball_table",
    "parse_hidden_item_table",
    "find_script_awarded_items",
    "parse_trainer_class_genders",
    "parse_trainer_class_prize_multipliers",
    "parse_trainer_record",
    "parse_trainer_battle_commands",
    "parse_static_encounter_commands",
    "parse_pokemon_gift_commands",
    "parse_mart_dispatch_commands",
    "parse_npc_trade_record",
    "parse_tutor_compatibility_table",
    "parse_tutor_move_table",
    "derive_trainer_party_attributes",
    "resolve_trainer_variants",
    "STARTER_BATTLE_OPCODE",
    "STARTER_SPECIES_ENTRY_SIZE",
    "Gen4StarterBranchFamily",
    "parse_starter_branch_families",
    "parse_starter_species",
    "normalize_trainer_party_member",
    "machine_name",
    "parse_personal_record",
    "parse_pickup_item_table",
    "pickup_level_range_item_ids",
    "parse_english_message_archive",
    "parse_move_record",
]


#: HeartGold/SoulSilver's trainer-battle command. This generation's two
#: leaves share the branch idiom but not this opcode: Platinum uses
#: 0x00E5, HGSS 0x00D5. Established two independent ways: (1) locating the
#: curated Silver groups in their own scripts, where each trainer ID is
#: preceded by 0x00D5, with the same compare/jump pair on variable 0x800C
#: guarding each branch; (2) scanning every opcode value across the full
#: script archive for the "valid trainer operand(s) plus a real follow-on
#: command" shape (see `hgss.scripts`) and cross-checking hits against the
#: already-decoded sight-triggered trainer set -- 0x00D5 produced 121 sites
#: across 49 files, 98% of them new trainers, forming a roster that reads
#: like the real game (all 8 Johto Gym Leaders in sequence, Silver's three
#: story battles, Team Rocket's three Executives).
STARTER_BATTLE_OPCODE = START_TRAINER_BATTLE


def parse_starter_branch_families(
    data: bytes,
    *,
    script_file_id: int,
    trainer_count: int,
    starter_species=None,
):
    """Decode this leaf's starter-selected battles (see `gen4.starter_branches`)."""
    return _parse_starter_branch_families(
        data,
        script_file_id=script_file_id,
        trainer_count=trainer_count,
        battle_opcode=STARTER_BATTLE_OPCODE,
        starter_species=starter_species,
    )

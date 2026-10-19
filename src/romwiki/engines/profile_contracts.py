from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from romwiki.util.errors import ProfileError


@dataclass(frozen=True, slots=True)
class EngineProfileContract:
    """Profile keys understood by one mature engine adapter."""

    required_layout: frozenset[str] = frozenset()
    optional_layout: frozenset[str] = frozenset()
    required_parameters: frozenset[str] = frozenset()
    optional_parameters: frozenset[str] = frozenset()
    reject_unknown: bool = False

    def validate(self, profile: Any) -> None:
        layout = getattr(profile, "layout", {})
        parameters = getattr(profile, "parameters", {})
        profile_id = getattr(profile, "id", "<unknown>")
        if not isinstance(layout, Mapping) or not all(
            isinstance(key, str) and isinstance(value, str) and bool(value)
            for key, value in layout.items()
        ):
            raise ProfileError(f"Profile {profile_id!r} has invalid layout entries")
        if not isinstance(parameters, Mapping) or not all(
            isinstance(key, str) for key in parameters
        ):
            raise ProfileError(f"Profile {profile_id!r} has invalid parameters")

        self._require(profile_id, "layout", set(layout), self.required_layout)
        self._require(
            profile_id,
            "parameters",
            set(parameters),
            self.required_parameters,
        )
        self._require_int_like_parameters(profile_id, parameters)
        if self.reject_unknown:
            self._reject_unknown(
                profile_id,
                "layout",
                set(layout),
                self.required_layout | self.optional_layout,
            )
            self._reject_unknown(
                profile_id,
                "parameters",
                set(parameters),
                self.required_parameters | self.optional_parameters,
            )

    @staticmethod
    def _require(
        profile_id: str,
        label: str,
        actual: set[str],
        required: frozenset[str],
    ) -> None:
        missing = sorted(required - actual)
        if missing:
            raise ProfileError(
                f"Profile {profile_id!r} is missing required {label}: "
                f"{', '.join(missing)}"
            )

    @staticmethod
    def _require_int_like_parameters(
        profile_id: str, parameters: Mapping[str, Any]
    ) -> None:
        """Catch a numeric ROM offset/count/ID parameter written as some
        other type in a profile TOML (e.g. a quoted string), which would
        otherwise only surface later as an unclear TypeError deep in
        extraction code.

        Scoped to names ending in `_offset`/`_count`/`_id` -- by this
        project's own naming convention, every parameter with one of these
        suffixes across all four profile contracts is genuinely int-typed
        (verified against every extraction module that reads one); this
        does not attempt to type-check parameters outside that convention
        (locators, contract IDs, exclusion lists, and similar).
        """
        invalid = sorted(
            name
            for name, value in parameters.items()
            if name.endswith(("_offset", "_count", "_id"))
            and (not isinstance(value, int) or isinstance(value, bool))
        )
        if invalid:
            raise ProfileError(
                f"Profile {profile_id!r} has non-integer values for parameters: "
                f"{', '.join(invalid)}"
            )

    @staticmethod
    def _reject_unknown(
        profile_id: str,
        label: str,
        actual: set[str],
        supported: frozenset[str],
    ) -> None:
        unknown = sorted(actual - supported)
        if unknown:
            raise ProfileError(
                f"Profile {profile_id!r} has unsupported {label}: {', '.join(unknown)}"
            )


# Optional so that a build no variant contract was verified against still
# publishes its trainers, without battle families.
_TRAINER_VARIANT_PARAMETERS = frozenset({"trainer_variant_contract"})
# Sizes of message tables a hack may resize; each defaults to the engine's
# retail size (see `pipeline/extraction/counts.py`).
_TABLE_COUNT_PARAMETERS = frozenset(
    {
        "ability_name_count",
        "item_name_count",
        "move_name_count",
        "pokemon_description_count",
        "pokemon_name_count",
        "type_name_count",
    }
)

GEN3_FRLG_PROFILE_CONTRACT = EngineProfileContract(
    # Generation III (Game Boy Advance) has no filesystem/archive concept --
    # data is addressed by fixed ROM offsets under `[parameters]`, not
    # `[layout]` path aliases like the Nintendo DS engines above.
    required_parameters=frozenset(
        {
            "personal_offset",
            "personal_count",
            "pokemon_name_offset",
            "pokemon_name_stride",
            "learnset_offset",
            "move_offset",
            "move_count",
            "move_name_offset",
            "move_name_stride",
            "move_name_count",
            "item_offset",
            "item_count",
            "trainer_offset",
            "trainer_count",
            "trainer_class_name_offset",
            "ability_name_offset",
            "ability_name_stride",
            "ability_name_count",
            "encounter_offset",
            "encounter_count",
            "region_name_offset",
            "region_name_count",
            "gmapgroups_offset",
            "evolution_offset",
            "tmhm_learnset_offset",
            "machine_move_offset",
            "machine_count",
            "tm_count",
            "egg_move_offset",
            "egg_move_table_size",
            "ability_description_offset",
            "move_description_offset",
            "tutor_move_offset",
            "tutor_compatibility_offset",
        }
    ),
    optional_parameters=frozenset(
        {
            "map_group_count",
            "rematch_table_count",
            "rematch_table_offset",
            "trade_count",
            "trade_table_offset",
            "trainer_class_count",
            "trainer_money_offset",
            "trainer_variant_contract",
        }
    ),
    reject_unknown=True,
)

GEN3_EMERALD_PROFILE_CONTRACT = EngineProfileContract(
    # Widen as more Generation III domains are verified against the real
    # Emerald ROM, matching how GEN3_FRLG_PROFILE_CONTRACT itself grew.
    required_parameters=frozenset(
        {
            "personal_offset",
            "personal_count",
            "pokemon_name_offset",
            "pokemon_name_stride",
            "learnset_offset",
            "ability_name_offset",
            "ability_name_stride",
            "ability_name_count",
            "ability_description_offset",
            "move_description_offset",
            "move_offset",
            "move_count",
            "move_name_offset",
            "move_name_stride",
            "move_name_count",
            "item_offset",
            "item_count",
            "trainer_offset",
            "trainer_count",
            "trainer_class_name_offset",
            "evolution_offset",
            "tmhm_learnset_offset",
            "machine_move_offset",
            "machine_count",
            "tm_count",
            "egg_move_offset",
            "egg_move_table_size",
            "tutor_move_offset",
            "tutor_compatibility_offset",
            "encounter_offset",
            "encounter_count",
            "region_name_offset",
            "region_name_count",
            "gmapgroups_offset",
        }
    ),
    optional_parameters=frozenset(
        {
            "map_group_count",
            "rematch_table_count",
            "rematch_table_offset",
            "trade_count",
            "trade_table_offset",
            "trainer_class_count",
            "trainer_money_offset",
            "trainer_variant_contract",
        }
    ),
    reject_unknown=True,
)

_GEN5_LAYOUT = frozenset(
    {
        "egg_moves",
        "encounters",
        "evolutions",
        "item_data",
        "learnsets",
        "map_headers",
        "map_matrices",
        "messages",
        "moves",
        "npc_trades",
        "overworld_objects",
        "personal",
        "scripts",
        "trainer_data",
        "trainer_parties",
    }
)
_GEN5_PARAMETERS = frozenset(
    {
        "ability_names_member",
        "ability_descriptions_member",
        "hidden_items_script_member",
        "item_balls_script_member",
        "item_names_member",
        "item_descriptions_member",
        "map_names_member",
        "move_names_member",
        "move_descriptions_member",
        "npc_trade_names_member",
        "npc_trades_unused",
        "pickup_overlay_id",
        "pokemon_names_member",
        "pokemon_descriptions_member",
        "trainer_classes_member",
        "trainer_names_member",
    }
)

GEN5_BW_PROFILE_CONTRACT = EngineProfileContract(
    required_layout=_GEN5_LAYOUT,
    required_parameters=_GEN5_PARAMETERS
    | {
        "shop_item_overlay_id",
        "starter_species_count",
        "starter_species_offset",
        "starter_species_overlay_id",
    },
    optional_parameters=_TRAINER_VARIANT_PARAMETERS | _TABLE_COUNT_PARAMETERS,
    reject_unknown=True,
)

GEN5_B2W2_PROFILE_CONTRACT = EngineProfileContract(
    required_layout=_GEN5_LAYOUT | {"hidden_grottos", "shop_items"},
    required_parameters=_GEN5_PARAMETERS
    | {
        "hidden_grotto_version_group",
        "hidden_grotto_dispatch_base",
        "hidden_grotto_record_count",
        "swarm_overlay_id",
        "swarm_record_count",
        "swarm_table_offset",
        "tutor_move_offset",
        "tutor_overlay_id",
    },
    optional_parameters=frozenset(
        {
            "encounters_allow_trailing_data",
            "field_archives_allow_incorrect_data_block_size",
            "field_archives_allow_trailing_data",
            "learnsets_allow_incorrect_data_block_size",
            "learnsets_allow_trailing_data",
            "map_headers_allow_trailing_data",
            "map_headers_allow_incorrect_data_block_size",
            "overworld_objects_unused",
            "pickup_table_locator",
            "repair_invalid_secondary_egg_group",
        }
    )
    | _TRAINER_VARIANT_PARAMETERS
    | _TABLE_COUNT_PARAMETERS,
    reject_unknown=True,
)

GEN4_PLATINUM_PROFILE_CONTRACT = EngineProfileContract(
    required_layout=frozenset(
        {
            "berry_data",
            "bonus_encounters",
            "encounters",
            "events",
            "evolutions",
            "item_data",
            "learnsets",
            "map_matrices",
            "map_names",
            "messages",
            "moves",
            "npc_trades",
            "personal",
            "scripts",
            "trainer_data",
            "trainer_parties",
        }
    ),
    required_parameters=frozenset(
        {
            "ability_names_member",
            "common_mart_inventory_offset",
            "decoration_mart_inventory_count",
            "decoration_mart_inventory_start",
            "decoration_name_count",
            "decoration_names_member",
            "decoration_price_table_offset",
            "egg_move_offset",
            "egg_move_overlay_id",
            "first_berry_item_id",
            "fossil_revival_count",
            "fossil_revival_table_offset",
            "frontier_mart_inventory_count",
            "frontier_price_overlay_id",
            "frontier_price_record_count",
            "frontier_price_table_offset",
            "game_corner_prize_count",
            "game_corner_prize_table_offset",
            "item_names_member",
            "location_names_member",
            "machine_move_offset",
            "map_header_count",
            "map_header_offset",
            "move_names_member",
            "npc_trade_names_member",
            "pickup_common_items_offset",
            "pickup_common_rate_offset",
            "pickup_honey_gather_rate_offset",
            "pickup_overlay_id",
            "pickup_rare_items_offset",
            "pokemon_names_member",
            "seal_mart_inventory_count",
            "seal_mart_inventory_start",
            "seal_names_member",
            "seal_price_table_offset",
            "special_tutors",
            "specialty_mart_inventory_count",
            "specialty_mart_pointer_table_offset",
            "static_encounter_locations",
            "trainer_class_gender_offset",
            "trainer_class_prize_offset",
            "trainer_class_prize_overlay_id",
            "trainer_classes_member",
            "trainer_names_member",
            "starter_species_count",
            "starter_species_offset",
            "starter_species_overlay_id",
            "trainer_rematch_count",
            "trainer_rematch_offset",
            "trainer_rematch_overlay_id",
            "tutor_compatibility_offset",
            "tutor_count",
            "tutor_move_offset",
            "tutor_overlay_id",
            "type_names_member",
        }
    ),
    optional_parameters=_TRAINER_VARIANT_PARAMETERS | _TABLE_COUNT_PARAMETERS,
    reject_unknown=True,
)

GEN4_HGSS_PROFILE_CONTRACT = EngineProfileContract(
    required_layout=frozenset(
        {
            "egg_moves",
            "encounters",
            "headbutt_encounters",
            "safari_encounters",
            "events",
            "evolutions",
            "item_data",
            "learnsets",
            "map_names",
            "map_matrices",
            "messages",
            "moves",
            "npc_trades",
            "personal",
            "scripts",
            "trainer_data",
            "trainer_parties",
            "tutor_compatibility",
        }
    ),
    required_parameters=frozenset(
        {
            "ability_names_member",
            "item_names_member",
            "location_names_member",
            "map_header_count",
            "map_header_offset",
            "move_names_member",
            "npc_trade_names_member",
            "null_encounter_id",
            "pickup_overlay_id",
            "shop_catalog_locator",
            "pokemon_names_member",
            "starter_species_count",
            "starter_species_offset",
            "starter_species_overlay_id",
            "trainer_class_gender_offset",
            "trainer_classes_member",
            "trainer_names_member",
            "tutor_move_offset",
            "tutor_overlay_id",
        }
    ),
    optional_parameters=frozenset(
        {
            "encounters_allow_truncated",
            "events_allow_incorrect_data_block_size",
            "evolutions_allow_truncated",
            "items_allow_truncated",
            "learnsets_allow_incorrect_data_block_size",
            "learnsets_allow_truncated",
            "messages_allow_truncated",
            "npc_trades_unused",
            "scripts_allow_incorrect_data_block_size",
            "scripts_allow_trailing_data",
            "trainer_archives_allow_truncated",
        }
    )
    | _TRAINER_VARIANT_PARAMETERS
    | _TABLE_COUNT_PARAMETERS,
    reject_unknown=True,
)

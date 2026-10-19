from __future__ import annotations

import json
from typing import Any

from romwiki.pipeline.semantics.encounter_identity import (
    CONDITIONAL_ENCOUNTER_SOURCES,
    encounter_dataset_format,
    encounter_route_key,
    is_unlinked_encounter_area,
)
from romwiki.schema.trainers import is_unused_trainer_slot
from romwiki.schema.versions import COMPARISON_SCHEMA_VERSION
from romwiki.util.errors import DataSourceError

RECORD_KEY_FIELDS = {
    "pokemon": "member",
    "abilities": "ability_id",
    "moves": "move_id",
    "items": "item_id",
    "wild_encounters": "area_id",
    "trainers": "trainer_id",
    "locations": "header_id",
    "trades": "trade_id",
}

_FIELDS = {
    "pokemon": (
        "name",
        "base_stats",
        "types",
        "abilities",
        "catch_rate",
        "base_experience",
        "ev_yields",
        "held_items",
        "gender_ratio",
        "hatch_cycles",
        "base_friendship",
        "growth_rate",
        "egg_groups",
        "safari_flee_rate",
        "body_color",
        "flip_sprite",
        "evolutions",
        "machines",
        "tutor_moves",
        "level_up_moves",
        "egg_moves",
    ),
    "abilities": ("name", "pokemon"),
    "moves": (
        "name",
        "type",
        "damage_class",
        "power",
        "accuracy",
        "pp",
        "priority",
        "effect_id",
        "effect_chance",
        "target_id",
        "flags",
        "contest_effect_id",
        "contest_type_id",
        "machines",
        "tutors",
        "egg_move_pokemon",
    ),
    "items": (
        "name",
        "price",
        "pocket",
        "field_pocket_id",
        "field_use",
        "field_use_function_id",
        "battle_use_function_id",
        "battle_pocket_mask",
        "hold_effect_id",
        "hold_effect_parameter",
        "pluck_effect_id",
        "fling_effect_id",
        "fling_power",
        "natural_gift_power",
        "natural_gift_type",
        "party_use",
        "party_effects",
        "prevent_toss",
        "selectable",
        "locations",
        "shops",
        "wild_held_by",
        "trainer_held_by",
        "trainer_battle_items",
        "gifts",
        "trades",
        "evolutions",
        "revives_into",
        "revives_at",
        "berry",
    ),
    "wild_encounters": (
        "active",
        "name",
        "source_type",
        "grotto_id",
        "header_id",
        "location",
        "pokemon",
        "pools",
        "tree_groups",
        "visible_items",
        "hidden_items",
        "species_id",
        "minimum_level",
        "maximum_level",
        "locations",
        "walking",
        "walking_variants",
        "surf",
        "rock_smash",
        "old_rod",
        "good_rod",
        "super_rod",
        "special",
        "encounter_form_rates",
        "unown_table_id",
        "grass_cave",
        "doubles_grass",
        "shaking_spots",
        "surfing",
        "surfing_spots",
        "fishing",
        "fishing_spots",
    ),
    "trainers": (
        "name",
        "class_id",
        "class_name",
        "battle_mode",
        "battle_type",
        "double_battle",
        "ai_flags",
        "ai_battle_items",
        "party",
        "locations",
        "script_references",
    ),
    "trades": (
        "offered_species_id",
        "offered_forme_id",
        "requested_species_id",
        "held_item_id",
        "offered_pokemon",
        "requested_pokemon",
    ),
    "locations": (
        "name",
        "internal_name",
        "location_name_id",
        "matrix_id",
        "area_data_id",
        "level_script_id",
        "text_archive_id",
        "day_music_id",
        "night_music_id",
        "weather_id",
        "camera_id",
        "map_flags",
        "event_file_id",
        "encounter_id",
        "connections",
        "warps",
        "items",
        "script_awarded_items",
        "shops",
        "pokemon_gifts",
        "npc_trades",
        "static_encounters",
        "roaming_activations",
        "trainers",
        "honey_tree",
        "daily_encounter_pool",
        "game_corner_prizes",
    ),
}

_UNORDERED = {
    "pokemon": {"machines", "tutor_moves", "egg_moves"},
    "abilities": {"pokemon"},
    "moves": {"machines", "tutors", "egg_move_pokemon"},
    "items": {
        "locations",
        "shops",
        "wild_held_by",
        "trainer_held_by",
        "trainer_battle_items",
        "gifts",
        "trades",
        "evolutions",
        "revives_at",
    },
    "trainers": {"locations", "script_references"},
    "locations": {
        "connections",
        "warps",
        "items",
        "script_awarded_items",
        "shops",
        "pokemon_gifts",
        "npc_trades",
        "static_encounters",
        "roaming_activations",
        "trainers",
    },
}

_LABELS = {
    "pokemon": "Pokémon",
    "base_stats": "Base stats",
    "base_experience": "Base experience",
    "ev_yields": "EV yield",
    "held_items": "Wild held items",
    "gender_ratio": "Gender ratio",
    "hatch_cycles": "Hatch cycles",
    "base_friendship": "Base friendship",
    "growth_rate": "Growth rate",
    "egg_groups": "Egg groups",
    "safari_flee_rate": "Safari flee rate",
    "body_color": "Body color",
    "flip_sprite": "Sprite orientation",
    "tutor_moves": "Move tutors",
    "level_up_moves": "Level-up moves",
    "egg_moves": "Egg moves",
    "damage_class": "Damage class",
    "effect_id": "Effect",
    "effect_chance": "Effect chance",
    "target_id": "Target",
    "contest_effect_id": "Contest effect",
    "contest_type_id": "Contest type",
    "field_pocket_id": "Field pocket",
    "field_use": "Field use",
    "field_use_function_id": "Field-use function",
    "battle_use_function_id": "Battle-use function",
    "battle_pocket_mask": "Battle pocket",
    "hold_effect_id": "Held effect",
    "hold_effect_parameter": "Held-effect parameter",
    "pluck_effect_id": "Pluck effect",
    "fling_effect_id": "Fling effect",
    "fling_power": "Fling power",
    "natural_gift_power": "Natural Gift power",
    "natural_gift_type": "Natural Gift type",
    "party_use": "Party use",
    "party_effects": "Party effects",
    "prevent_toss": "Prevents tossing",
    "location_name_id": "Location-name index",
    "matrix_id": "Matrix ID",
    "area_data_id": "Area data ID",
    "level_script_id": "Level script",
    "text_archive_id": "Text archive",
    "day_music_id": "Day music",
    "night_music_id": "Night music",
    "weather_id": "Weather",
    "camera_id": "Camera",
    "map_flags": "Map flags",
    "event_file_id": "Event file",
    "encounter_id": "Encounter area",
    "old_rod": "Old Rod",
    "good_rod": "Good Rod",
    "super_rod": "Super Rod",
    "grass_cave": "Grass/Cave",
    "doubles_grass": "Doubles Grass",
    "shaking_spots": "Shaking Spots",
    "surfing_spots": "Surfing Spots",
    "fishing_spots": "Fishing Spots",
    "unknown_value": "Unknown engine value",
    "ai_flags": "AI flags",
    "battle_type": "Battle type",
    "roaming_activations": "Roaming activations",
    "ai_battle_items": "AI battle items",
    "trainer_battle_items": "Trainer battle items",
    "script_references": "Script references",
}

_DISPLAY_KEYS = {"name", "slug", "label", "internal_name", "class_name"}
_IDENTITY_KEYS = {
    "id",
    "member",
    "ability_id",
    "area_id",
    "event_file_id",
    "header_id",
    "item_id",
    "location_name_id",
    "machine_id",
    "matrix_id",
    "move_id",
    "species_id",
    "table_index",
    "trainer_id",
}


def compare_datasets(
    current: dict[str, Any], baseline: dict[str, Any]
) -> dict[str, Any]:
    kind = current.get("dataset")
    if kind != baseline.get("dataset") or kind not in RECORD_KEY_FIELDS:
        raise DataSourceError("Comparison datasets must have the same supported kind")
    current_records = _published_records(current, kind)
    baseline_records = _published_records(baseline, kind)
    records = []
    counts = dict.fromkeys(("unchanged", "changed", "added", "removed"), 0)
    for key in sorted(
        set(current_records) | set(baseline_records), key=_record_identity_sort_key
    ):
        after = current_records.get(key)
        before = baseline_records.get(key)
        changes: list[dict[str, Any]]
        if before is None:
            status = "added"
            changes = []
        elif after is None:
            status = "removed"
            changes = []
        else:
            changes = _field_changes(kind, before, after)
            status = "changed" if changes else "unchanged"
        counts[status] += 1
        record = after or before
        assert record is not None
        value = {
            "kind": kind,
            "key": key,
            "status": status,
            "label": _record_label(kind, record),
            "slug": (
                encounter_route_key(record)
                if kind == "wild_encounters"
                else record.get("slug")
            ),
            "detail_available": after is not None and _has_detail_page(kind, after),
            "changes": changes,
        }
        if status == "removed":
            assert before is not None
            value["baseline_record"] = _snapshot(kind, before)
        records.append(value)
    return {
        "schema_version": COMPARISON_SCHEMA_VERSION,
        "dataset": f"{kind}_comparison",
        "kind": kind,
        "game": current["game"],
        "baseline": baseline["game"],
        "source": {
            "current_rom_sha256": current.get("source", {}).get("rom_sha256"),
            "baseline_rom_sha256": baseline.get("source", {}).get("rom_sha256"),
        },
        "coverage": list(_FIELDS[kind]),
        "counts": counts,
        "records": records,
    }


def _published_records(
    dataset: dict[str, Any], kind: str
) -> dict[int | str, dict[str, Any]]:
    records = records_by_identity(dataset, kind)
    if kind != "wild_encounters":
        return records
    # An area going from reachable to unlinked (or back) reads as removed
    # (or added), which is what changed from a player's point of view.
    encounter_format = encounter_dataset_format(dataset)
    return {
        key: record
        for key, record in records.items()
        if not is_unlinked_encounter_area(record, encounter_format)
    }


def comparison_by_key(
    dataset: dict[str, Any] | None,
) -> dict[int | str, dict[str, Any]]:
    if dataset is None:
        return {}
    return {record["key"]: record for record in dataset.get("records", [])}


def record_identity(kind: str, record: dict[str, Any]) -> int | str:
    if (
        kind == "wild_encounters"
        and record.get("source_type") in CONDITIONAL_ENCOUNTER_SOURCES
    ):
        return encounter_route_key(record)
    return record[RECORD_KEY_FIELDS[kind]]


def records_by_identity(
    dataset: dict[str, Any], kind: str
) -> dict[int | str, dict[str, Any]]:
    records = dataset.get("records")
    if not isinstance(records, list):
        raise DataSourceError("Comparison dataset records must be a list")
    result = {record_identity(kind, record): record for record in records}
    if len(result) != len(records):
        raise DataSourceError(f"Comparison identities must be unique: {kind}")
    return result


def _record_identity_sort_key(value: int | str) -> tuple[str, int | str]:
    return type(value).__name__, value


def records_semantically_equal(
    kind: str, first: dict[str, Any], second: dict[str, Any]
) -> bool:
    """Compare only the normalized fields published for one dataset kind."""
    if kind not in _FIELDS:
        raise DataSourceError(f"Unsupported comparison kind: {kind}")
    return not _field_changes(kind, first, second)


def _field_changes(
    kind: str, before: dict[str, Any], after: dict[str, Any]
) -> list[dict[str, Any]]:
    changes = []
    for field in _FIELDS[kind]:
        previous = _clean(before.get(field))
        current = _clean(after.get(field))
        previous_semantic = normalize_comparison_value(previous, kind=kind, field=field)
        current_semantic = normalize_comparison_value(current, kind=kind, field=field)
        if field in _UNORDERED.get(kind, set()):
            equal = _canonical_set(previous_semantic) == _canonical_set(
                current_semantic
            )
        else:
            equal = previous_semantic == current_semantic
        if not equal:
            changes.append(
                {
                    "field": field,
                    "label": _LABELS.get(field, field.replace("_", " ").title()),
                    "before": previous,
                    "after": current,
                }
            )
    return changes


def _snapshot(kind: str, record: dict[str, Any]) -> dict[str, Any]:
    return {field: _clean(record.get(field)) for field in _FIELDS[kind]}


def _clean(value: Any) -> Any:
    if isinstance(value, (list, tuple)):
        return [_clean(item) for item in value]
    if not isinstance(value, dict):
        return value
    return {
        key: _clean(item)
        for key, item in value.items()
        if key
        not in {
            "provenance",
            "reference",
            "source_fields",
            "sprite",
            "sprites",
            # A raw ROM file offset (`TrainerLocation.script_id`, the
            # trainerbattle script's address), not game content -- two
            # independently-compiled sibling ROMs (e.g. FireRed/LeafGreen)
            # place the same logical script at different addresses even
            # when every other field of the same trainer-location match
            # (verified: FireRed/LeafGreen trainer 89's own location record
            # differs only in this field). Distinct from the unrelated
            # `level_script_id` field (Gen IV map headers' real, meaningful
            # "which script runs on entering this map" content), which
            # stays compared.
            "script_id",
        }
        and not key.endswith("_provenance")
    }


def normalize_comparison_value(
    value: Any,
    *,
    kind: str | None = None,
    field: str | None = None,
) -> Any:
    """Remove presentation labels where a stable ROM identity is available."""
    if isinstance(value, list) and kind == "pokemon":
        if field == "machines":
            return [item.get("id") for item in value]
        if field in {"egg_moves", "tutor_moves"}:
            return [(item.get("move") or item).get("id") for item in value]
        if field in {"abilities", "types", "egg_groups"}:
            return [item.get("id") for item in value]
        if field == "level_up_moves":
            return [
                {"level": item.get("level"), "move_id": item["move"].get("id")}
                for item in value
            ]
        if field == "held_items":
            return [
                {"rarity": item.get("rarity"), "item_id": item.get("id")}
                for item in value
            ]
    if isinstance(value, list) and kind == "moves":
        if field == "machines":
            return [item.get("id") for item in value]
        if field == "egg_move_pokemon":
            return [item.get("member", item.get("id")) for item in value]
    if isinstance(value, (list, tuple)):
        return [normalize_comparison_value(item) for item in value]
    if not isinstance(value, dict):
        return value
    has_identity = any(key in value for key in _IDENTITY_KEYS) or any(
        key.endswith("_id") for key in value
    )
    return {
        key: normalize_comparison_value(item)
        for key, item in value.items()
        if not (has_identity and key in _DISPLAY_KEYS)
    }


def _canonical_set(value: Any) -> list[str]:
    if not isinstance(value, list):
        return [json.dumps(value, sort_keys=True, ensure_ascii=False)]
    return sorted(
        json.dumps(item, sort_keys=True, ensure_ascii=False) for item in value
    )


def _record_label(kind: str, record: dict[str, Any]) -> str:
    if kind == "trainers":
        parts = (record.get("class_name"), record.get("name"))
        return " ".join(part for part in parts if part)
    return str(
        record.get("name")
        or record.get("internal_name")
        or record.get(RECORD_KEY_FIELDS[kind])
    )


def _has_detail_page(kind: str, record: dict[str, Any]) -> bool:
    if kind in {"pokemon", "moves"}:
        return bool(record.get("public"))
    if kind == "trainers":
        return bool(record.get("party")) and not is_unused_trainer_slot(record)
    if kind == "wild_encounters":
        return bool(record.get("active"))
    return True

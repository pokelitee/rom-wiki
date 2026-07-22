from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from romwiki.util.errors import DataSourceError
from romwiki.util.json_io import write_json_atomic
from romwiki.schema.versions import COMPARISON_SCHEMA_VERSION


_KEYS = {
    "pokemon": "member",
    "abilities": "ability_id",
    "moves": "move_id",
    "items": "item_id",
    "wild_encounters": "area_id",
    "trainers": "trainer_id",
    "locations": "header_id",
}

_FIELDS = {
    "pokemon": (
        "name", "base_stats", "types", "abilities", "catch_rate",
        "base_experience", "ev_yields", "held_items", "gender_ratio",
        "hatch_cycles", "base_friendship", "growth_rate", "egg_groups",
        "safari_flee_rate", "body_color", "flip_sprite", "evolutions",
        "machines", "tutor_moves", "level_up_moves", "egg_moves",
    ),
    "abilities": ("name", "pokemon"),
    "moves": (
        "name", "type", "damage_class", "power", "accuracy", "pp",
        "priority", "effect_id", "effect_chance", "target_id", "flags",
        "contest_effect_id", "contest_type_id", "machines", "tutors",
        "egg_move_pokemon",
    ),
    "items": (
        "name", "price", "pocket", "field_pocket_id", "field_use",
        "field_use_function_id", "battle_use_function_id", "battle_pocket_mask",
        "hold_effect_id", "hold_effect_parameter", "pluck_effect_id",
        "fling_effect_id", "fling_power", "natural_gift_power",
        "natural_gift_type", "party_use", "party_effects", "prevent_toss",
        "selectable", "locations", "shops", "wild_held_by", "trainer_held_by",
        "trainer_battle_items", "gifts", "trades", "evolutions",
    ),
    "wild_encounters": (
        "active", "name", "locations", "walking", "surf", "old_rod",
        "good_rod", "super_rod", "special", "unknown_value",
    ),
    "trainers": (
        "name", "class_id", "class_name", "double_battle", "ai_flags",
        "ai_battle_items", "party", "locations", "script_references",
    ),
    "locations": (
        "name", "internal_name", "location_name_id", "matrix_id",
        "event_file_id", "encounter_id", "connections", "warps", "items",
        "shops", "pokemon_gifts", "npc_trades", "static_encounters", "trainers",
    ),
}

_UNORDERED = {
    "pokemon": {"machines", "tutor_moves", "egg_moves"},
    "abilities": {"pokemon"},
    "moves": {"machines", "tutors", "egg_move_pokemon"},
    "items": {
        "locations", "shops", "wild_held_by", "trainer_held_by",
        "trainer_battle_items", "gifts", "trades", "evolutions",
    },
    "trainers": {"locations", "script_references"},
    "locations": {
        "connections", "warps", "items", "shops", "pokemon_gifts",
        "npc_trades", "static_encounters", "trainers",
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
    "location_name_id": "Location-name ID",
    "matrix_id": "Matrix ID",
    "event_file_id": "Event file",
    "encounter_id": "Encounter area",
    "old_rod": "Old Rod",
    "good_rod": "Good Rod",
    "super_rod": "Super Rod",
    "unknown_value": "Unknown engine value",
    "ai_flags": "AI flags",
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
    if kind != baseline.get("dataset") or kind not in _KEYS:
        raise DataSourceError("Comparison datasets must have the same supported kind")
    key_name = _KEYS[kind]
    current_records = _records_by_key(current, key_name)
    baseline_records = _records_by_key(baseline, key_name)
    records = []
    counts = {status: 0 for status in ("unchanged", "changed", "added", "removed")}
    for key in sorted(set(current_records) | set(baseline_records)):
        after = current_records.get(key)
        before = baseline_records.get(key)
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
        value = {
            "kind": kind,
            "key": key,
            "status": status,
            "label": _record_label(kind, record),
            "slug": record.get("slug"),
            "detail_available": after is not None and _has_detail_page(kind, after),
            "changes": changes,
        }
        if status == "removed":
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


def write_comparison_dataset(dataset: dict[str, Any], output_path: Path) -> None:
    write_json_atomic(output_path, dataset)


def comparison_by_key(
    dataset: dict[str, Any] | None,
) -> dict[int | str, dict[str, Any]]:
    if dataset is None:
        return {}
    return {record["key"]: record for record in dataset.get("records", [])}


def _records_by_key(
    dataset: dict[str, Any], key_name: str
) -> dict[int | str, dict[str, Any]]:
    records = dataset.get("records")
    if not isinstance(records, list):
        raise DataSourceError("Comparison dataset records must be a list")
    result = {record[key_name]: record for record in records}
    if len(result) != len(records):
        raise DataSourceError(f"Comparison keys must be unique: {key_name}")
    return result


def _field_changes(
    kind: str, before: dict[str, Any], after: dict[str, Any]
) -> list[dict[str, Any]]:
    changes = []
    for field in _FIELDS[kind]:
        previous = _clean(before.get(field))
        current = _clean(after.get(field))
        previous_semantic = normalize_comparison_value(
            previous, kind=kind, field=field
        )
        current_semantic = normalize_comparison_value(
            current, kind=kind, field=field
        )
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
        not in {"provenance", "reference", "source_fields", "sprite", "sprites"}
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
            return [
                (item.get("move") or item).get("id")
                for item in value
            ]
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
    return sorted(json.dumps(item, sort_keys=True, ensure_ascii=False) for item in value)


def _record_label(kind: str, record: dict[str, Any]) -> str:
    if kind == "trainers":
        parts = (record.get("class_name"), record.get("name"))
        return " ".join(part for part in parts if part)
    return str(record.get("name") or record.get("internal_name") or record.get(_KEYS[kind]))


def _has_detail_page(kind: str, record: dict[str, Any]) -> bool:
    if kind in {"pokemon", "moves"}:
        return bool(record.get("public"))
    if kind == "trainers":
        return bool(record.get("party"))
    if kind == "wild_encounters":
        return bool(record.get("active"))
    return True

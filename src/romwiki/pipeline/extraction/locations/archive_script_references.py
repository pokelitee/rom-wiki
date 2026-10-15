from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator
from itertools import chain
from typing import Any

from romwiki.engines.concerns import LocationConcern
from romwiki.schema import LocationScriptAwardedItem, LocationStaticEncounter


def resolve_script_locations(
    engine: LocationConcern,
    headers: tuple[Any, ...],
    script_file_ids: tuple[int, ...],
    scripts: Any,
    overworld_objects: Any,
    *,
    unused_overworld_members: frozenset[int] = frozenset(),
) -> dict[int, tuple[int, ...]]:
    """Map dedicated and common script members to every proven map caller."""
    member_count = len(scripts.members)
    owners: dict[int, set[int]] = defaultdict(set)
    for header in headers:
        owners[script_file_ids[header.header_id]].add(header.header_id)
        if (
            header.overworld_file_id >= len(overworld_objects.members)
            or header.overworld_file_id in unused_overworld_members
        ):
            continue
        overworld = overworld_objects.read(header.overworld_file_id)
        references = [npc.script_used for npc in engine.parse_overworld_npcs(overworld)]
        references.extend(
            furniture.script_used
            for furniture in engine.parse_overworld_furniture(overworld)
        )
        for reference in references:
            member = engine.resolve_common_script_member(
                reference, member_count=member_count
            )
            if member is not None:
                owners[member].add(header.header_id)

    return {
        member: tuple(sorted(header_ids))
        for member, header_ids in owners.items()
        if header_ids
    }


def extract_script_awarded_items(
    engine: LocationConcern,
    scripts: Any,
    script_headers: dict[int, tuple[int, ...]],
    item_dataset: dict[str, Any] | None,
) -> dict[int, list[LocationScriptAwardedItem]]:
    item_names = {
        record["item_id"]: record["name"]
        for record in (item_dataset or {}).get("records", ())
    }
    if not item_names:
        return {}
    item_count = max(item_names) + 1
    references: dict[int, list[LocationScriptAwardedItem]] = defaultdict(list)
    seen: set[tuple[int, int, int]] = set()
    for member, header_ids in script_headers.items():
        for award in engine.find_script_awarded_items(
            scripts.read(member), item_count=item_count
        ):
            if award.item_id not in item_names:
                continue
            for header_id in header_ids:
                identity = (header_id, member, award.command_offset)
                if identity in seen:
                    continue
                seen.add(identity)
                references[header_id].append(
                    LocationScriptAwardedItem(
                        item_id=award.item_id,
                        name=item_names[award.item_id],
                        quantity=award.quantity,
                        script_file_id=member,
                        command_offset=award.command_offset,
                        command=award.command,
                    )
                )
    for values in references.values():
        values.sort(key=lambda item: (item.script_file_id, item.command_offset))
    return references


def extract_npc_trade_references(
    engine: LocationConcern,
    profile: Any,
    messages: Any,
    map_header_data: bytes,
    scripts: Any,
    script_headers: dict[int, tuple[int, ...]],
    trade_dataset: dict[str, Any] | None,
    item_dataset: dict[str, Any] | None,
) -> dict[int, list[dict[str, Any]]]:
    if trade_dataset is None:
        return {}
    records_by_id = {
        record["trade_id"]: record for record in trade_dataset.get("records", ())
    }
    if not records_by_id:
        return {}
    pokemon_names = engine.parse_english_message_archive(
        messages.read(profile.int_parameter("pokemon_names_member"))
    )
    item_names = {
        record["item_id"]: record["name"]
        for record in (item_dataset or {}).get("records", ())
    }
    references: dict[int, list[dict[str, Any]]] = defaultdict(list)
    seen: set[tuple[int, int]] = set()
    for trade_id, header_id, member, offset in chain(
        _script_trade_calls(engine, scripts, script_headers, records_by_id),
        _text_archive_trade_calls(engine, map_header_data),
    ):
        record = records_by_id.get(trade_id)
        identity = (trade_id, header_id)
        if record is None or identity in seen:
            continue
        seen.add(identity)
        references[header_id].append(
            {
                **record,
                "requested_species_name": pokemon_names[record["requested_species_id"]],
                "offered_species_name": pokemon_names[record["offered_species_id"]],
                "held_item_name": item_names.get(record.get("held_item_id")),
                "script_file_id": member,
                "command_offset": offset,
            }
        )

    for values in references.values():
        values.sort(key=lambda value: value["trade_id"])
    return references


def _script_trade_calls(
    engine: LocationConcern,
    scripts: Any,
    script_headers: dict[int, tuple[int, ...]],
    records_by_id: dict[int, dict[str, Any]],
) -> Iterator[tuple[int, int, int, int]]:
    """Yield `(trade_id, header_id, script member, command offset)` per call."""
    trade_count = max(records_by_id) + 1
    for member, header_ids in script_headers.items():
        script = scripts.read(member)
        for function_offset in engine.parse_function_offsets(script):
            for offset, trade_id in _function_trade_ids(
                engine, script, function_offset, trade_count
            ):
                if trade_id not in records_by_id:
                    continue
                for header_id in header_ids:
                    yield trade_id, header_id, member, offset


def _function_trade_ids(
    engine: LocationConcern, script: bytes, function_offset: int, trade_count: int
) -> Iterator[tuple[int, int]]:
    """Yield `(command offset, trade_id)` for each trade one function can start.

    A `FieldTradeStart` operand outside the trade-ID range is a work variable,
    resolved through every constant the same function assigns to it.
    """
    instructions = tuple(engine.disassemble_function(script, function_offset).values())
    assignments: dict[int, set[int]] = defaultdict(set)
    for instruction in instructions:
        if instruction.name in {"WorkSet", "WorkSetConst"}:
            assignments[instruction.params[0]].add(instruction.params[1])
    for instruction in instructions:
        if instruction.name != "FieldTradeStart":
            continue
        operand = instruction.params[0]
        candidates = (
            {operand} if 0 <= operand < trade_count else assignments.get(operand, set())
        )
        for trade_id in candidates:
            yield instruction.offset, trade_id


def _text_archive_trade_calls(
    engine: LocationConcern, map_header_data: bytes
) -> Iterator[tuple[int, int, int, int]]:
    text_mapping = engine.NPC_TRADE_TEXT_MEMBER_BY_ID
    if not text_mapping:
        return
    text_file_ids = engine.parse_map_header_text_files(map_header_data)
    headers_by_text: dict[int, list[int]] = defaultdict(list)
    for header_id, text_file_id in enumerate(text_file_ids):
        headers_by_text[text_file_id].append(header_id)
    for trade_id, text_file_id in text_mapping.items():
        for header_id in headers_by_text.get(text_file_id, ()):
            yield trade_id, header_id, -1, -1


def extract_static_encounter_references(
    engine: LocationConcern,
    profile: Any,
    messages: Any,
    script_headers: dict[int, tuple[int, ...]],
    static_encounter_dataset: dict[str, Any] | None,
) -> dict[int, list[LocationStaticEncounter]]:
    """Resolve static (gift/single) Pokémon encounters to a real map header.

    Each fact is a `[script-file, byte-offset]` pair into `layout.scripts`
    (see `pipeline/extraction/static_encounters.py`); this cross-references the same
    script file against each map header's own dedicated script file (the
    same field §4's trainer-battle-trigger work decoded) rather than
    guessing. Dedicated scripts resolve through map headers; secondary/common
    scripts resolve through proven overworld references. The latter includes
    the museum's shared fossil-revival script.
    """
    if static_encounter_dataset is None:
        return {}
    pokemon_names_member = profile.optional_int_parameter("pokemon_names_member")
    if pokemon_names_member is None:
        return {}
    pokemon_names = engine.parse_english_message_archive(
        messages.read(pokemon_names_member)
    )
    references: dict[int, list[LocationStaticEncounter]] = defaultdict(list)
    for record in static_encounter_dataset["records"]:
        provenance = record.get("provenance", {})
        species_file = provenance.get("member")
        species_offset = record.get("command_offset")
        if not isinstance(species_file, int) or not isinstance(species_offset, int):
            continue
        header_ids = script_headers.get(species_file, ())
        if not header_ids:
            continue
        for header_id in header_ids:
            references[header_id].append(
                LocationStaticEncounter(
                    species_id=record["species_id"],
                    name=pokemon_names[record["species_id"]],
                    level=record["level"],
                    is_egg=record["is_egg"],
                    command=record.get("command") or "StaticPokemon",
                    script_file_id=species_file,
                    command_offset=species_offset,
                )
            )
    for values in references.values():
        values.sort(key=lambda item: (item.name, item.level or 0))
    return references

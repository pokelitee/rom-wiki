"""Generation III per-map facts from map events and event scripts.

Every map's warps, connections, item balls, hidden items, static
encounters, gifts, handed-over items, and marts, read from its `MapEvents`,
`MapConnections`, and the scripts its objects, signs, triggers, and map
scripts run (see `engines/gen3/shared/scripts.py`). Facts come from literal
script commands only; a value held in a script variable is left out.
"""

from __future__ import annotations

import struct
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

from romwiki.engines.common.script_control_flow import ScriptInstruction
from romwiki.pipeline.extraction.map_headers import GbaMapHeader
from romwiki.schema import (
    LocationConnection,
    LocationItem,
    LocationNpcTrade,
    LocationPokemonGift,
    LocationScriptAwardedItem,
    LocationShop,
    LocationShopItem,
    LocationStaticEncounter,
    LocationWarp,
)
from romwiki.util.errors import InvalidRomError

# Generation III scripts aren't stored in files: commands are identified by
# their ROM offset alone.
_SCRIPT_FILE_ID = 0
# `MapHeader` pointers to the map's events, map scripts, and connections.
_EVENTS_POINTER = 0x04
_MAP_SCRIPTS_POINTER = 0x08
_CONNECTIONS_POINTER = 0x0C
# Map script types 2 and 4 (`MAP_SCRIPT_ON_FRAME_TABLE`,
# `MAP_SCRIPT_ON_WARP_INTO_MAP_TABLE`) point to tables of (u16 var, u16
# value, script) entries ending at var 0; the other types point straight
# to a script.
_SCRIPT_TABLE_TYPES = frozenset({2, 4})
_SCRIPT_TABLE_ENTRY_SIZE = 8
_MAP_SCRIPT_ENTRY_SIZE = 5


@dataclass(slots=True)
class GbaMapFacts:
    warps: list[LocationWarp] = field(default_factory=list)
    connections: list[LocationConnection] = field(default_factory=list)
    items: list[LocationItem] = field(default_factory=list)
    script_awarded_items: list[LocationScriptAwardedItem] = field(default_factory=list)
    static_encounters: list[LocationStaticEncounter] = field(default_factory=list)
    pokemon_gifts: list[LocationPokemonGift] = field(default_factory=list)
    shops: list[LocationShop] = field(default_factory=list)
    npc_trades: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class GbaMapNames:
    species: Sequence[str]
    items: Mapping[int, str]
    item_prices: Mapping[int, int]
    # The ROM's `sIngameTrades`, or empty when the profile doesn't locate it.
    trades: Sequence[Any] = ()


def extract_gba_map_facts(
    engine: Any,
    read: Callable[[int, int], bytes],
    headers: Sequence[GbaMapHeader],
    names: GbaMapNames,
) -> tuple[dict[int, GbaMapFacts], int]:
    """Facts for each map, keyed by header ID, and the number of object
    scripts that couldn't be decoded (a hack can point an object at unused
    bytes).
    """
    by_map = {(header.map_group, header.map_num): header for header in headers}
    warp_counts = {
        key: _warp_count(engine, read, header) for key, header in by_map.items()
    }
    facts: dict[int, GbaMapFacts] = {}
    undecoded = 0
    for header in headers:
        result = GbaMapFacts()
        events = _events(engine, read, header)
        scripts: dict[int, ScriptInstruction] = {}
        if events is not None:
            result.warps = _warps(engine, read, events, by_map, warp_counts)
            undecoded += _object_events(engine, read, events, names, result, scripts)
            _bg_events(engine, read, events, names, result, scripts)
            _coord_events(engine, read, events, scripts)
        _map_scripts(engine, read, header, scripts)
        result.connections = _connections(engine, read, header, by_map)
        _script_facts(engine, read, scripts, names, result)
        facts[header.header_id] = result
    return facts, undecoded


def map_object_scripts(
    engine: Any,
    read: Callable[[int, int], bytes],
    headers: Sequence[GbaMapHeader],
) -> dict[int, ScriptInstruction]:
    """Every instruction reachable from any map's object scripts."""
    scripts: dict[int, ScriptInstruction] = {}
    for header in headers:
        events = _events(engine, read, header)
        if events is None:
            continue
        objects = _array(
            engine,
            read,
            events.objects_pointer,
            events.object_count,
            engine.OBJECT_EVENT_TEMPLATE_SIZE,
        )
        for index, raw in enumerate(objects):
            _, kind, *_rest, script = engine.parse_object_event_template(
                raw, header_id=header.header_id, index=index
            )
            if kind == 0 and script:
                scripts.update(_disassemble(engine, read, script))
    return scripts


def _pointer(header: GbaMapHeader, offset: int) -> int:
    return int(struct.unpack_from("<I", header.data, offset)[0])


def _events(
    engine: Any, read: Callable[[int, int], bytes], header: GbaMapHeader
) -> Any:
    pointer = _pointer(header, _EVENTS_POINTER)
    if not pointer:
        return None
    return engine.parse_gba_map_events(
        read(engine.resolve_gba_pointer(pointer), engine.GBA_MAP_EVENTS_SIZE)
    )


def _warp_count(
    engine: Any, read: Callable[[int, int], bytes], header: GbaMapHeader
) -> int:
    events = _events(engine, read, header)
    return 0 if events is None else int(events.warp_count)


def _array(
    engine: Any,
    read: Callable[[int, int], bytes],
    pointer: int,
    count: int,
    size: int,
) -> list[bytes]:
    if not pointer or not count:
        return []
    data = read(engine.resolve_gba_pointer(pointer), size * count)
    return [data[index * size : (index + 1) * size] for index in range(count)]


def _warps(
    engine: Any,
    read: Callable[[int, int], bytes],
    events: Any,
    by_map: Mapping[tuple[int, int], GbaMapHeader],
    warp_counts: Mapping[tuple[int, int], int],
) -> list[LocationWarp]:
    warps = []
    for index, raw in enumerate(
        _array(
            engine,
            read,
            events.warps_pointer,
            events.warp_count,
            engine.WARP_EVENT_SIZE,
        )
    ):
        warp = engine.parse_warp_event(raw)
        key = (warp.map_group, warp.map_num)
        destination = by_map.get(key)
        dynamic = key == engine.DYNAMIC_MAP
        warps.append(
            LocationWarp(
                index=index,
                x=warp.x,
                z=warp.y,
                destination_header_id=destination.header_id if destination else None,
                destination_warp_id=None if dynamic else warp.warp_id,
                destination_name=destination.name if destination else None,
                destination_section_name=None,
                destination_internal_name=None,
                destination_warp_exists=(
                    warp.warp_id < warp_counts[key] if destination else None
                ),
                dynamic=dynamic,
            )
        )
    return warps


def _object_events(
    engine: Any,
    read: Callable[[int, int], bytes],
    events: Any,
    names: GbaMapNames,
    result: GbaMapFacts,
    scripts: dict[int, ScriptInstruction],
) -> int:
    undecoded = 0
    objects = _array(
        engine,
        read,
        events.objects_pointer,
        events.object_count,
        engine.OBJECT_EVENT_TEMPLATE_SIZE,
    )
    for index, raw in enumerate(objects):
        _local_id, kind, x, y, elevation, _trainer_type, script = (
            engine.parse_object_event_template(raw, header_id=0, index=index)
        )
        # A clone object reuses the layout for another map's object.
        if kind != 0 or not script:
            continue
        instructions = _disassemble(engine, read, script)
        if not instructions:
            undecoded += 1
            continue
        scripts.update(instructions)
        ball = engine.find_item_ball(instructions)
        if ball is not None:
            result.items.append(
                LocationItem(
                    item_id=ball.item_id,
                    name=names.items.get(ball.item_id, f"Item {ball.item_id}"),
                    kind="visible",
                    event_index=index,
                    x=x,
                    z=y,
                    y=elevation,
                    hidden_flag=None,
                )
            )
    return undecoded


def _bg_events(
    engine: Any,
    read: Callable[[int, int], bytes],
    events: Any,
    names: GbaMapNames,
    result: GbaMapFacts,
    scripts: dict[int, ScriptInstruction],
) -> None:
    for index, raw in enumerate(
        _array(engine, read, events.bgs_pointer, events.bg_count, engine.BG_EVENT_SIZE)
    ):
        event = engine.parse_bg_event(raw)
        if event.kind == engine.BG_EVENT_HIDDEN_ITEM:
            item_id, _quantity, flag = engine.decode_hidden_item(event.value)
            if item_id:
                result.items.append(
                    LocationItem(
                        item_id=item_id,
                        name=names.items.get(item_id, f"Item {item_id}"),
                        kind="hidden",
                        event_index=index,
                        x=event.x,
                        z=event.y,
                        y=event.elevation,
                        hidden_flag=flag,
                    )
                )
        elif event.kind in engine.BG_EVENT_SCRIPT_KINDS and event.value:
            scripts.update(_disassemble(engine, read, event.value))


def _coord_events(
    engine: Any,
    read: Callable[[int, int], bytes],
    events: Any,
    scripts: dict[int, ScriptInstruction],
) -> None:
    for raw in _array(
        engine, read, events.coords_pointer, events.coord_count, engine.COORD_EVENT_SIZE
    ):
        script = engine.parse_coord_event_script(raw)
        if script:
            scripts.update(_disassemble(engine, read, script))


def _map_scripts(
    engine: Any,
    read: Callable[[int, int], bytes],
    header: GbaMapHeader,
    scripts: dict[int, ScriptInstruction],
) -> None:
    pointer = _pointer(header, _MAP_SCRIPTS_POINTER)
    if not pointer:
        return
    offset = engine.resolve_gba_pointer(pointer)
    while (entry := read(offset, _MAP_SCRIPT_ENTRY_SIZE))[0]:
        kind, target = entry[0], int.from_bytes(entry[1:], "little")
        if kind in _SCRIPT_TABLE_TYPES:
            table = engine.resolve_gba_pointer(target)
            while (row := read(table, _SCRIPT_TABLE_ENTRY_SIZE))[:2] != b"\0\0":
                scripts.update(
                    _disassemble(engine, read, int.from_bytes(row[4:], "little"))
                )
                table += _SCRIPT_TABLE_ENTRY_SIZE
        else:
            scripts.update(_disassemble(engine, read, target))
        offset += _MAP_SCRIPT_ENTRY_SIZE


def _connections(
    engine: Any,
    read: Callable[[int, int], bytes],
    header: GbaMapHeader,
    by_map: Mapping[tuple[int, int], GbaMapHeader],
) -> list[LocationConnection]:
    pointer = _pointer(header, _CONNECTIONS_POINTER)
    if not pointer:
        return []
    count, connections_pointer = engine.parse_map_connections(
        read(engine.resolve_gba_pointer(pointer), engine.MAP_CONNECTIONS_SIZE)
    )
    directions: dict[int, list[str]] = {}
    for raw in _array(
        engine, read, connections_pointer, count, engine.MAP_CONNECTION_SIZE
    ):
        connection = engine.parse_map_connection(raw)
        destination = (
            by_map.get((connection.map_group, connection.map_num))
            if connection is not None
            else None
        )
        if connection is not None and destination is not None:
            directions.setdefault(destination.header_id, []).append(
                connection.direction
            )
    names = {header.header_id: header.name for header in by_map.values()}
    return [
        LocationConnection(
            destination_header_id=header_id,
            destination_name=names[header_id],
            destination_internal_name="",
            directions=tuple(found),
        )
        for header_id, found in directions.items()
    ]


def _script_facts(
    engine: Any,
    read: Callable[[int, int], bytes],
    scripts: Mapping[int, ScriptInstruction],
    names: GbaMapNames,
    result: GbaMapFacts,
) -> None:
    for item in engine.find_given_items(scripts):
        result.script_awarded_items.append(
            LocationScriptAwardedItem(
                item_id=item.item_id,
                name=names.items.get(item.item_id, f"Item {item.item_id}"),
                quantity=item.quantity,
                script_file_id=_SCRIPT_FILE_ID,
                command_offset=engine.resolve_gba_pointer(item.offset),
                command="giveitem",
            )
        )
    for pokemon in engine.find_pokemon(
        scripts,
        species_count=len(names.species),
        event_mon_special=engine.EVENT_MON_SPECIAL,
    ):
        name = names.species[pokemon.species_id]
        offset = engine.resolve_gba_pointer(pokemon.offset)
        if pokemon.kind == "static":
            result.static_encounters.append(
                LocationStaticEncounter(
                    species_id=pokemon.species_id,
                    name=name,
                    level=pokemon.level,
                    is_egg=False,
                    command="setwildbattle",
                    script_file_id=_SCRIPT_FILE_ID,
                    command_offset=offset,
                )
            )
        else:
            result.pokemon_gifts.append(
                LocationPokemonGift(
                    kind=pokemon.kind,
                    species_id=pokemon.species_id,
                    name=name,
                    level=pokemon.level or 0,
                    held_item_id=pokemon.held_item_id,
                    held_item_name=(
                        names.items.get(pokemon.held_item_id)
                        if pokemon.held_item_id
                        else None
                    ),
                    script_file_id=_SCRIPT_FILE_ID,
                    command_offset=offset,
                )
            )
    for mart in engine.find_marts(scripts, read):
        result.shops.append(
            LocationShop(
                kind="mart",
                currency="money",
                inventory_id=None,
                script_file_id=_SCRIPT_FILE_ID,
                command_offset=engine.resolve_gba_pointer(mart.offset),
                items=tuple(
                    LocationShopItem(
                        item_id=item_id,
                        name=names.items.get(item_id, f"Item {item_id}"),
                        price=names.item_prices.get(item_id),
                        required_badges=None,
                    )
                    for item_id in mart.item_ids
                ),
                inventory_source="script",
            )
        )
    for trade_id, offset in engine.find_trades(
        scripts,
        trade_count=len(names.trades),
        trade_info_special=engine.TRADE_INFO_SPECIAL,
    ):
        result.npc_trades.append(
            _npc_trade(engine, names, trade_id, engine.resolve_gba_pointer(offset))
        )


def _npc_trade(
    engine: Any, names: GbaMapNames, trade_id: int, offset: int
) -> dict[str, Any]:
    trade = names.trades[trade_id]
    held_item_id = trade.held_item_id or None
    return asdict(
        LocationNpcTrade(
            trade_id=trade_id,
            requested_species_id=trade.requested_species_id,
            requested_species_name=names.species[trade.requested_species_id],
            offered_species_id=trade.species_id,
            offered_species_name=names.species[trade.species_id],
            nickname=trade.nickname,
            ivs=trade.ivs,
            nature=engine.NATURE_NAMES[trade.personality % len(engine.NATURE_NAMES)],
            held_item_id=held_item_id,
            held_item_name=names.items.get(held_item_id) if held_item_id else None,
            ot_name=trade.ot_name,
            ot_id=trade.ot_id,
            ot_gender="Female" if trade.ot_gender else "Male",
            # Generation III trades store no language.
            language="",
            personality=trade.personality,
            contest_stats=(*trade.conditions, trade.sheen),
            unused_values=(),
            script_file_id=_SCRIPT_FILE_ID,
            command_offset=offset,
        )
    )


def _disassemble(
    engine: Any, read: Callable[[int, int], bytes], start: int
) -> dict[int, ScriptInstruction]:
    try:
        engine.resolve_gba_pointer(start)
    except InvalidRomError:
        return {}
    return dict(
        engine.disassemble_script(
            read,
            start,
            commands=engine.SCRIPT_COMMANDS,
            warps=engine.SCRIPT_WARP_COMMANDS,
        )
    )

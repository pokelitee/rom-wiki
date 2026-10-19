from __future__ import annotations

import struct
from collections.abc import Callable

import romwiki.engines.gen3.frlg as frlg
from romwiki.pipeline.extraction.locations.gba_map_events import (
    GbaMapNames,
    extract_gba_map_facts,
)
from romwiki.pipeline.extraction.map_headers import GbaMapHeader
from romwiki.util.errors import InvalidRomError

_GBA = 0x08000000


def _ptr(offset: int) -> int:
    return _GBA + offset


def _map_rom() -> tuple[bytes, list[GbaMapHeader]]:
    """Two maps. Map 0.0 has a warp to 0.1, a connection north to 0.1, an
    item-ball object, a hidden item, a sign that gives a Pokémon, and a
    map script that opens a mart. Map 0.1 has one warp back.
    """
    rom = bytearray(0x400)
    # Map 0.0 events at 0x100: 1 object, 1 warp, 0 coords, 2 bg events.
    struct.pack_into(
        "<4B4I", rom, 0x100, 1, 1, 0, 2, _ptr(0x120), _ptr(0x140), 0, _ptr(0x150)
    )
    # Object 0: normal kind, at (4, 5), script at 0x200.
    struct.pack_into("<BBBxhhB", rom, 0x120, 1, 0, 0, 4, 5, 3)
    struct.pack_into("<I", rom, 0x120 + 0x10, _ptr(0x200))
    # Warp to map 0.1 (mapNum 1, mapGroup 0), warp 0.
    struct.pack_into("<hh4B", rom, 0x140, 6, 7, 0, 0, 1, 0)
    # Hidden Potion (packed: item 13, flag 2, quantity 1), then a sign.
    struct.pack_into("<HHBBxxI", rom, 0x150, 8, 9, 0, 7, 13 | (2 << 16) | (1 << 24))
    struct.pack_into("<HHBBxxI", rom, 0x15C, 1, 1, 0, 0, _ptr(0x220))
    # Item ball: finditem Poké Ball (4), 1.
    rom[0x200:0x20D] = (
        b"\x1a"
        + struct.pack("<HH", 0x8000, 4)
        + b"\x1a"
        + struct.pack("<HH", 0x8001, 1)
        + b"\x09\x01\x02"
    )
    # Sign: givemon Eevee (133) Lv25; end.
    rom[0x220:0x230] = b"\x79" + struct.pack("<HBH", 133, 25, 0) + bytes(9) + b"\x02"
    # Map script (type 1, on load): pokemart at 0x2C0, end.
    struct.pack_into("<BI", rom, 0x240, 1, _ptr(0x260))
    rom[0x260:0x266] = b"\x86" + struct.pack("<I", _ptr(0x2C0)) + b"\x02"
    struct.pack_into("<3H", rom, 0x2C0, 4, 13, 0)
    # Connections: one, north to map 0.1.
    struct.pack_into("<iI", rom, 0x280, 1, _ptr(0x290))
    struct.pack_into("<BxxxiBBxx", rom, 0x290, 2, 0, 0, 1)
    # Map 0.1 events at 0x300: one warp back to 0.0.
    struct.pack_into("<4B4I", rom, 0x300, 0, 1, 0, 0, 0, _ptr(0x320), 0, 0)
    struct.pack_into("<hh4B", rom, 0x320, 1, 1, 0, 0, 0, 0)

    def header(events: int, scripts: int, connections: int) -> bytes:
        data = bytearray(28)
        struct.pack_into("<4I", data, 0, 0, events, scripts, connections)
        return bytes(data)

    headers = [
        GbaMapHeader(0, 0, 0, 0, header(_ptr(0x100), _ptr(0x240), _ptr(0x280)), "Town"),
        GbaMapHeader(1, 0, 1, 0, header(_ptr(0x300), 0, 0), "House"),
    ]
    return bytes(rom), headers


def _reader(rom: bytes) -> Callable[[int, int], bytes]:
    def read(offset: int, size: int) -> bytes:
        if offset + size > len(rom):
            raise InvalidRomError("past the end")
        return rom[offset : offset + size]

    return read


def test_extracts_each_maps_events_and_script_facts() -> None:
    rom, headers = _map_rom()
    names = GbaMapNames(
        species=["?"] * 133 + ["Eevee"] + ["?"] * 278,
        items={4: "Poké Ball", 13: "Potion"},
        item_prices={4: 200, 13: 300},
    )

    facts, undecoded = extract_gba_map_facts(frlg, _reader(rom), headers, names)

    town, house = facts[0], facts[1]
    assert undecoded == 0
    assert [(w.destination_name, w.destination_warp_exists) for w in town.warps] == [
        ("House", True)
    ]
    assert [w.destination_name for w in house.warps] == ["Town"]
    assert [(c.destination_name, c.directions) for c in town.connections] == [
        ("House", ("north",))
    ]
    assert [(i.name, i.kind, i.x, i.z, i.hidden_flag) for i in town.items] == [
        ("Poké Ball", "visible", 4, 5, None),
        ("Potion", "hidden", 8, 9, 2),
    ]
    assert [(g.name, g.level) for g in town.pokemon_gifts] == [("Eevee", 25)]
    assert [[(i.name, i.price) for i in shop.items] for shop in town.shops] == [
        [("Poké Ball", 200), ("Potion", 300)]
    ]

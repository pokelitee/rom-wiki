from __future__ import annotations

import struct

from romwiki.engines.common.script_control_flow import ScriptInstruction
from romwiki.engines.gen3.shared.script_facts import (
    find_given_items,
    find_item_ball,
    find_marts,
    find_menu_costs,
    find_pokemon,
    find_trades,
)

_GBA = 0x08000000
_EVENT_MON_SPECIAL = 482


def _script(
    *commands: tuple[int, str, tuple[int, ...], int],
) -> dict[int, ScriptInstruction]:
    """Chain commands given as (opcode, name, params, length)."""
    instructions, address = {}, _GBA
    for opcode, name, params, length in commands:
        instructions[address] = ScriptInstruction(
            offset=address,
            opcode=opcode,
            name=name,
            params=params,
            next_offset=address + length,
        )
        address += length
    return instructions


def _std_item(item: int, quantity: int, std: int) -> dict[int, ScriptInstruction]:
    return _script(
        (0x1A, "setorcopyvar", (0x8000, item), 5),
        (0x1A, "setorcopyvar", (0x8001, quantity), 5),
        (0x09, "callstd", (std,), 2),
        (0x02, "end", (), 1),
    )


def test_item_ball_is_finditem() -> None:
    ball = find_item_ball(_std_item(13, 1, std=1))
    assert ball is not None
    assert (ball.item_id, ball.quantity) == (13, 1)
    assert find_item_ball(_std_item(13, 1, std=0)) is None


def test_given_items_include_giveitem_and_additem_but_not_variables() -> None:
    script = _std_item(339, 1, std=0)
    script.update(
        {
            _GBA + 0x40: ScriptInstruction(
                _GBA + 0x40, 0x44, "additem", (20, 2), _GBA + 0x45
            ),
            _GBA + 0x50: ScriptInstruction(
                _GBA + 0x50, 0x44, "additem", (0x4001, 1), _GBA + 0x55
            ),
        }
    )

    assert [(item.item_id, item.quantity) for item in find_given_items(script)] == [
        (339, 1),
        (20, 2),
    ]


def test_pokemon_from_wild_battles_event_mons_gifts_and_eggs() -> None:
    script = _script(
        (0xB6, "setwildbattle", (150, 70, 0), 6),
        (0x16, "setvar", (0x8004, 410), 5),
        (0x16, "setvar", (0x8005, 30), 5),
        (0x16, "setvar", (0x8006, 0), 5),
        (0x25, "special", (_EVENT_MON_SPECIAL,), 3),
        (0x79, "givemon", (133, 25, 0, 0, 0, 0), 15),
        (0x7A, "giveegg", (175,), 3),
        (0x79, "givemon", (999, 25, 0, 0, 0, 0), 15),
    )

    found = find_pokemon(
        script, species_count=412, event_mon_special=_EVENT_MON_SPECIAL
    )

    assert [(p.kind, p.species_id, p.level) for p in found] == [
        ("static", 150, 70),
        ("static", 410, 30),
        ("pokemon", 133, 25),
        ("egg", 175, None),
    ]


def test_mart_reads_its_product_list() -> None:
    rom = bytearray(0x40)
    struct.pack_into("<4H", rom, 0x20, 4, 13, 18, 0)
    script = _script((0x86, "pokemart", (_GBA + 0x20,), 5))

    marts = find_marts(script, lambda offset, size: bytes(rom[offset : offset + size]))

    assert [mart.item_ids for mart in marts] == [(4, 13, 18)]


def test_trades_need_the_trade_info_special() -> None:
    script = _script(
        (0x16, "setvar", (0x8008, 2), 5),
        (0x19, "copyvar", (0x8004, 0x8008), 5),
        (0x26, "specialvar", (0x800D, 255), 5),
        (0x16, "setvar", (0x8008, 9), 5),
    )

    assert [
        trade_id
        for trade_id, _ in find_trades(script, trade_count=4, trade_info_special=255)
    ] == [2]
    assert find_trades(script, trade_count=4, trade_info_special=252) == ()


def test_menu_costs_follow_each_case_to_its_cost() -> None:
    menu = _script(
        (0x16, "setvar", (0x400E, 1), 5),
        (0x25, "special", (474,), 3),
        (0x19, "copyvar", (0x8000, 0x800D), 5),
        (0x21, "compare", (0x8000, 0), 5),
        (0x06, "goto_if", (1, _GBA + 0x100), 6),
        (0x21, "compare", (0x8000, 1), 5),
        (0x06, "goto_if", (1, _GBA + 0x110), 6),
    )
    menu.update(
        {
            _GBA + 0x100: ScriptInstruction(
                _GBA + 0x100, 0x16, "setvar", (0x8008, 16), _GBA + 0x105
            ),
            _GBA + 0x110: ScriptInstruction(
                _GBA + 0x110, 0x16, "setvar", (0x8008, 48), _GBA + 0x115
            ),
        }
    )

    assert find_menu_costs(menu, selector_var=0x400E) == {(1, 0): 16, (1, 1): 48}

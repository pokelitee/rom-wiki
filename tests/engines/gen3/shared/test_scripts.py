from __future__ import annotations

import struct
from collections.abc import Callable

from romwiki.engines.common.script_control_flow import ScriptInstruction
from romwiki.engines.gen3.emerald.script_commands import (
    SCRIPT_COMMANDS,
    SCRIPT_WARP_COMMANDS,
)
from romwiki.engines.gen3.shared.scripts import disassemble_script
from romwiki.util.errors import InvalidRomError

_GBA = 0x08000000


def _reader(rom: bytes) -> Callable[[int, int], bytes]:
    def read(offset: int, size: int) -> bytes:
        if offset + size > len(rom):
            raise InvalidRomError("past the end")
        return rom[offset : offset + size]

    return read


def _disassemble(rom: bytes, start: int = 0) -> dict[int, ScriptInstruction]:
    return disassemble_script(
        _reader(rom),
        _GBA + start,
        commands=SCRIPT_COMMANDS,
        warps=SCRIPT_WARP_COMMANDS,
    )


def _ptr(offset: int) -> bytes:
    return struct.pack("<I", _GBA + offset)


def test_follows_branches_calls_and_jumps() -> None:
    rom = bytearray(0x40)
    # 0x00 goto_if 1, 0x10; 0x06 call 0x18; 0x0B goto 0x20
    rom[0x00:0x06] = b"\x06\x01" + _ptr(0x10)
    rom[0x06:0x0B] = b"\x04" + _ptr(0x18)
    rom[0x0B:0x10] = b"\x05" + _ptr(0x20)
    rom[0x10] = 0x02  # end
    rom[0x18] = 0x03  # return
    rom[0x20] = 0x02  # end
    rom[0x30] = 0x02  # unreachable

    assert sorted(_disassemble(bytes(rom))) == [
        _GBA + offset for offset in (0x00, 0x06, 0x0B, 0x10, 0x18, 0x20)
    ]


def test_trainerbattle_length_and_post_battle_script_depend_on_type() -> None:
    rom = bytearray(0x40)
    # trainerbattle CONTINUE_SCRIPT (2): trainer 7, local id 0, two texts,
    # then the post-battle script at 0x30: 18 bytes, so `end` follows at 0x12.
    rom[0x00:0x12] = (
        b"\x5c\x02" + struct.pack("<HH", 7, 0) + _ptr(0x20) + _ptr(0x24) + _ptr(0x30)
    )
    rom[0x12] = 0x02
    rom[0x30] = 0x02

    instructions = _disassemble(bytes(rom))

    battle = instructions[_GBA]
    assert battle.params[:3] == (2, 7, 0)
    assert sorted(instructions) == [_GBA, _GBA + 0x12, _GBA + 0x30]


def test_a_warp_ends_the_run_because_data_may_follow() -> None:
    rom = bytearray(0x20)
    # warp map 0.1, warp 0, x/y -1; then movement data, not code.
    rom[0x00:0x08] = b"\x39\x00\x01\x00\xff\xff\xff\xff"
    rom[0x08] = 0xFE

    assert list(_disassemble(bytes(rom))) == [_GBA]


def test_unknown_opcodes_and_targets_outside_the_rom_end_a_path() -> None:
    rom = bytearray(0x10)
    rom[0x00:0x05] = b"\x05" + struct.pack("<I", 0x0A000000)
    assert list(_disassemble(bytes(rom))) == [_GBA]
    assert _disassemble(b"\xff") == {}

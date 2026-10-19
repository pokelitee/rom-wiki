"""Static disassembler for Generation III event scripts.

A command is a one-byte opcode followed by fixed-width little-endian
operands; jump and call targets are absolute ROM addresses. The operand
widths come from pret/pokefirered's and pret/pokeemerald's
`asm/macros/event.inc` (each command's primitive macro) and
`data/script_cmd_table.inc` (its opcode). The two games share opcodes
0x00-0xC6; each leaf adds its own later commands.

Disassembling every script reachable from every map's object, coordinate,
sign, and map-script events decodes about 25,000 FireRed/LeafGreen and
49,000 Emerald instructions with no unknown opcode and no jump outside the
ROM, which a single wrong width would break.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from romwiki.engines.common.script_control_flow import ScriptInstruction
from romwiki.util.errors import InvalidRomError

from .pointers import resolve_gba_pointer

ScriptCommandTable = Mapping[int, tuple[str, tuple[int, ...]]]

COMMON_SCRIPT_COMMANDS: dict[int, tuple[str, tuple[int, ...]]] = {
    0x00: ("nop", ()),
    0x01: ("nop1", ()),
    0x02: ("end", ()),
    0x03: ("return", ()),
    0x04: ("call", (4,)),
    0x05: ("goto", (4,)),
    0x06: ("goto_if", (1, 4)),
    0x07: ("call_if", (1, 4)),
    0x08: ("gotostd", (1,)),
    0x09: ("callstd", (1,)),
    0x0A: ("gotostd_if", (1, 1)),
    0x0B: ("callstd_if", (1, 1)),
    0x0C: ("returnram", ()),
    0x0D: ("endram", ()),
    0x0E: ("setmysteryeventstatus", (1,)),
    0x0F: ("loadword", (1, 4)),
    0x10: ("loadbyte", (1, 1)),
    0x11: ("setptr", (1, 4)),
    0x12: ("loadbytefromptr", (1, 4)),
    0x13: ("setptrbyte", (1, 4)),
    0x14: ("copylocal", (1, 1)),
    0x15: ("copybyte", (4, 4)),
    0x16: ("setvar", (2, 2)),
    0x17: ("addvar", (2, 2)),
    0x18: ("subvar", (2, 2)),
    0x19: ("copyvar", (2, 2)),
    0x1A: ("setorcopyvar", (2, 2)),
    0x1B: ("compare_local_to_local", (1, 1)),
    0x1C: ("compare_local_to_value", (1, 1)),
    0x1D: ("compare_local_to_ptr", (1, 4)),
    0x1E: ("compare_ptr_to_local", (4, 1)),
    0x1F: ("compare_ptr_to_value", (4, 1)),
    0x20: ("compare_ptr_to_ptr", (4, 4)),
    0x21: ("compare_var_to_value", (2, 2)),
    0x22: ("compare_var_to_var", (2, 2)),
    0x23: ("callnative", (4,)),
    0x24: ("gotonative", (4,)),
    0x25: ("special", (2,)),
    0x26: ("specialvar", (2, 2)),
    0x27: ("waitstate", ()),
    0x28: ("delay", (2,)),
    0x29: ("setflag", (2,)),
    0x2A: ("clearflag", (2,)),
    0x2B: ("checkflag", (2,)),
    0x2C: ("initclock", (2, 2)),
    0x2D: ("dotimebasedevents", ()),
    0x2E: ("gettime", ()),
    0x2F: ("playse", (2,)),
    0x30: ("waitse", ()),
    0x31: ("playfanfare", (2,)),
    0x32: ("waitfanfare", ()),
    0x33: ("playbgm", (2, 1)),
    0x34: ("savebgm", (2,)),
    0x35: ("fadedefaultbgm", ()),
    0x36: ("fadenewbgm", (2,)),
    0x37: ("fadeoutbgm", (1,)),
    0x38: ("fadeinbgm", (1,)),
    0x39: ("warp", (2, 1, 2, 2)),
    0x3A: ("warpsilent", (2, 1, 2, 2)),
    0x3B: ("warpdoor", (2, 1, 2, 2)),
    0x3C: ("warphole", (2,)),
    0x3D: ("warpteleport", (2, 1, 2, 2)),
    0x3E: ("setwarp", (2, 1, 2, 2)),
    0x3F: ("setdynamicwarp", (2, 1, 2, 2)),
    0x40: ("setdivewarp", (2, 1, 2, 2)),
    0x41: ("setholewarp", (2, 1, 2, 2)),
    0x42: ("getplayerxy", (2, 2)),
    0x43: ("getpartysize", ()),
    0x44: ("additem", (2, 2)),
    0x45: ("removeitem", (2, 2)),
    0x46: ("checkitemspace", (2, 2)),
    0x47: ("checkitem", (2, 2)),
    0x48: ("checkitemtype", (2,)),
    0x49: ("addpcitem", (2, 2)),
    0x4A: ("checkpcitem", (2, 2)),
    0x4B: ("adddecoration", (2,)),
    0x4C: ("removedecoration", (2,)),
    0x4D: ("checkdecor", (2,)),
    0x4E: ("checkdecorspace", (2,)),
    0x4F: ("applymovement", (2, 4)),
    0x50: ("applymovementat", (2, 4, 2)),
    0x51: ("waitmovement", (2,)),
    0x52: ("waitmovementat", (2, 2)),
    0x53: ("removeobject", (2,)),
    0x54: ("removeobjectat", (2, 2)),
    0x55: ("addobject", (2,)),
    0x56: ("addobjectat", (2, 2)),
    0x57: ("setobjectxy", (2, 2, 2)),
    0x58: ("showobjectat", (2, 2)),
    0x59: ("hideobjectat", (2, 2)),
    0x5A: ("faceplayer", ()),
    0x5B: ("turnobject", (2, 1)),
    0x5C: ("trainerbattle", (1, 2, 2)),
    0x5D: ("dotrainerbattle", ()),
    0x5E: ("gotopostbattlescript", ()),
    0x5F: ("gotobeatenscript", ()),
    0x60: ("checktrainerflag", (2,)),
    0x61: ("settrainerflag", (2,)),
    0x62: ("cleartrainerflag", (2,)),
    0x63: ("setobjectxyperm", (2, 2, 2)),
    0x64: ("copyobjectxytoperm", (2,)),
    0x65: ("setobjectmovementtype", (2, 1)),
    0x66: ("waitmessage", ()),
    0x67: ("message", (4,)),
    0x68: ("closemessage", ()),
    0x69: ("lockall", ()),
    0x6A: ("lock", ()),
    0x6B: ("releaseall", ()),
    0x6C: ("release", ()),
    0x6D: ("waitbuttonpress", ()),
    0x6E: ("yesnobox", (1, 1)),
    0x6F: ("multichoice", (1, 1, 1, 1)),
    0x70: ("multichoicedefault", (1, 1, 1, 1, 1)),
    0x71: ("multichoicegrid", (1, 1, 1, 1, 1)),
    0x72: ("drawbox", ()),
    0x73: ("erasebox", (1, 1, 1, 1)),
    0x74: ("drawboxtext", (1, 1, 1, 1)),
    0x75: ("showmonpic", (2, 1, 1)),
    0x76: ("hidemonpic", ()),
    0x77: ("showcontestpainting", (1,)),
    0x78: ("braillemessage", (4,)),
    0x79: ("givemon", (2, 1, 2, 4, 4, 1)),
    0x7A: ("giveegg", (2,)),
    0x7B: ("setmonmove", (1, 1, 2)),
    0x7C: ("checkpartymove", (2,)),
    0x7D: ("bufferspeciesname", (1, 2)),
    0x7E: ("bufferleadmonspeciesname", (1,)),
    0x7F: ("bufferpartymonnick", (1, 2)),
    0x80: ("bufferitemname", (1, 2)),
    0x81: ("bufferdecorationname", (1, 2)),
    0x82: ("buffermovename", (1, 2)),
    0x83: ("buffernumberstring", (1, 2)),
    0x84: ("bufferstdstring", (1, 2)),
    0x85: ("bufferstring", (1, 4)),
    0x86: ("pokemart", (4,)),
    0x87: ("pokemartdecoration", (4,)),
    0x88: ("pokemartdecoration2", (4,)),
    0x89: ("playslotmachine", (2,)),
    0x8A: ("setberrytree", (1, 1, 1)),
    0x8B: ("choosecontestmon", ()),
    0x8C: ("startcontest", ()),
    0x8D: ("showcontestresults", ()),
    0x8E: ("contestlinktransfer", ()),
    0x8F: ("random", (2,)),
    0x90: ("addmoney", (4, 1)),
    0x91: ("removemoney", (4, 1)),
    0x92: ("checkmoney", (4, 1)),
    0x93: ("showmoneybox", (1, 1, 1)),
    0x94: ("hidemoneybox", (1, 1)),
    0x95: ("updatemoneybox", (1, 1, 1)),
    0x96: ("getpokenewsactive", (2,)),
    0x97: ("fadescreen", (1,)),
    0x98: ("fadescreenspeed", (1, 1)),
    0x99: ("setflashlevel", (2,)),
    0x9A: ("animateflash", (1,)),
    0x9B: ("messageautoscroll", (4,)),
    0x9C: ("dofieldeffect", (2,)),
    0x9D: ("setfieldeffectargument", (1, 2)),
    0x9E: ("waitfieldeffect", (2,)),
    0x9F: ("setrespawn", (2,)),
    0xA0: ("checkplayergender", ()),
    0xA1: ("playmoncry", (2, 2)),
    0xA2: ("setmetatile", (2, 2, 2, 2)),
    0xA3: ("resetweather", ()),
    0xA4: ("setweather", (2,)),
    0xA5: ("doweather", ()),
    0xA6: ("setstepcallback", (1,)),
    0xA7: ("setmaplayoutindex", (2,)),
    0xA8: ("setobjectsubpriority", (2, 2, 1)),
    0xA9: ("resetobjectsubpriority", (2, 2)),
    0xAA: ("createvobject", (1, 1, 2, 2, 1, 1)),
    0xAB: ("turnvobject", (1, 1)),
    0xAC: ("opendoor", (2, 2)),
    0xAD: ("closedoor", (2, 2)),
    0xAE: ("waitdooranim", ()),
    0xAF: ("setdooropen", (2, 2)),
    0xB0: ("setdoorclosed", (2, 2)),
    0xB1: ("addelevmenuitem", (1, 2, 2, 2)),
    0xB2: ("showelevmenu", ()),
    0xB3: ("checkcoins", (2,)),
    0xB4: ("addcoins", (2,)),
    0xB5: ("removecoins", (2,)),
    0xB6: ("setwildbattle", (2, 1, 2)),
    0xB7: ("dowildbattle", ()),
    0xB8: ("setvaddress", (4,)),
    0xB9: ("vgoto", (4,)),
    0xBA: ("vcall", (4,)),
    0xBB: ("vgoto_if", (1, 4)),
    0xBC: ("vcall_if", (1, 4)),
    0xBD: ("vmessage", (4,)),
    0xBE: ("vbuffermessage", (4,)),
    0xBF: ("vbufferstring", (1, 4)),
    0xC0: ("showcoinsbox", (1, 1)),
    0xC1: ("hidecoinsbox", (1, 1)),
    0xC2: ("updatecoinsbox", (1, 1)),
    0xC3: ("incrementgamestat", (1,)),
    0xC4: ("setescapewarp", (2, 1, 2, 2)),
    0xC5: ("waitmoncry", ()),
    0xC6: ("bufferboxname", (1, 2)),
}

GOTO = 0x05
GOTO_IF = 0x06
CALL = 0x04
CALL_IF = 0x07
TRAINER_BATTLE = 0x5C
# `end`, `return`, `gotostd`, `returnram`/`endram`, `gotonative`, and the
# post-battle jumps end a straight-line run. So do warps (each leaf lists
# its own): a warp loads another map, so scripts often omit the `end` after
# one and the following bytes are data (an Emerald script ends `warp`,
# `waitstate`, then movement data).
_TERMINATORS = frozenset({0x02, 0x03, 0x08, 0x0C, 0x0D, 0x24, 0x5E, 0x5F})
COMMON_WARP_COMMANDS = frozenset({0x39, 0x3A, 0x3B, 0x3C, 0x3D})

# `trainerbattle type, trainer, local_id` is followed by a battle-type-
# dependent number of pointers; for some types the last is a script run
# after the battle. Types 9-12 differ by game and all take two text pointers.
_TRAINER_BATTLE_POINTERS = {0: 2, 1: 3, 2: 3, 3: 1, 4: 3, 5: 2, 6: 4, 7: 3, 8: 4}
_TRAINER_BATTLE_EXTRA_TYPES = range(9, 13)
_TRAINER_BATTLE_SCRIPT_TYPES = frozenset({1, 2, 6, 8})


def disassemble_script(
    read: Callable[[int, int], bytes],
    start: int,
    *,
    commands: ScriptCommandTable,
    warps: frozenset[int],
) -> dict[int, ScriptInstruction]:
    """Disassemble every instruction statically reachable from the script
    at ROM address `start`, keyed by ROM address.

    `read(offset, size)` returns ROM bytes and raises `InvalidRomError` past
    the end. An unknown opcode, an unreadable command, or a jump outside the
    ROM ends that path rather than raising: a hack can leave an object
    pointing at unused bytes (FireRed Omega has one).
    """
    instructions: dict[int, ScriptInstruction] = {}
    worklist = [start]
    while worklist:
        address = worklist.pop()
        while address not in instructions:
            instruction = _decode(read, address, commands)
            if instruction is None:
                break
            instructions[address] = instruction
            opcode, params = instruction.opcode, instruction.params
            if opcode in (GOTO, CALL):
                worklist.append(params[0])
            elif opcode in (GOTO_IF, CALL_IF):
                worklist.append(params[1])
            elif opcode == TRAINER_BATTLE and params[0] in _TRAINER_BATTLE_SCRIPT_TYPES:
                worklist.append(params[-1])
            if opcode == GOTO or opcode in _TERMINATORS or opcode in warps:
                break
            address = instruction.next_offset
    return instructions


def _decode(
    read: Callable[[int, int], bytes], address: int, commands: ScriptCommandTable
) -> ScriptInstruction | None:
    try:
        offset = resolve_gba_pointer(address)
        opcode = read(offset, 1)[0]
        entry = commands.get(opcode)
        if entry is None:
            return None
        name, widths = entry
        if opcode == TRAINER_BATTLE:
            kind = read(offset + 1, 1)[0]
            count = _TRAINER_BATTLE_POINTERS.get(kind)
            if count is None and kind in _TRAINER_BATTLE_EXTRA_TYPES:
                count = 2
            if count is None:
                return None
            widths = (*widths, *(4,) * count)
        data = read(offset + 1, sum(widths))
    except InvalidRomError:
        return None
    params, cursor = [], 0
    for width in widths:
        params.append(int.from_bytes(data[cursor : cursor + width], "little"))
        cursor += width
    return ScriptInstruction(
        offset=address,
        opcode=opcode,
        name=name,
        params=tuple(params),
        next_offset=address + 1 + cursor,
    )

"""Emerald event-script commands after the shared 0x00-0xC6 range,
from pret/pokeemerald's `asm/macros/event.inc` and
`data/script_cmd_table.inc`.
"""

from __future__ import annotations

from romwiki.engines.gen3.shared.scripts import (
    COMMON_SCRIPT_COMMANDS,
    COMMON_WARP_COMMANDS,
)

SCRIPT_COMMANDS: dict[int, tuple[str, tuple[int, ...]]] = {
    **COMMON_SCRIPT_COMMANDS,
    0xC7: ("nop1", (1,)),
    0xC8: ("nop1", (4,)),
    0xC9: ("nop1", ()),
    0xCA: ("nop1", ()),
    0xCB: ("nop1", ()),
    0xCC: ("nop1", (1, 4)),
    0xCD: ("setmodernfatefulencounter", (2,)),
    0xCE: ("checkmodernfatefulencounter", (2,)),
    0xCF: ("trywondercardscript", ()),
    0xD0: ("nop1", (2,)),
    0xD1: ("warpspinenter", (2, 1, 2, 2)),
    0xD2: ("setmonmetlocation", (2, 1)),
    0xD3: ("moverotatingtileobjects", (2,)),
    0xD4: ("turnrotatingtileobjects", ()),
    0xD5: ("initrotatingtilepuzzle", (2,)),
    0xD6: ("freerotatingtilepuzzle", ()),
    0xD7: ("warpmossdeepgym", (2, 1, 2, 2)),
    0xD8: ("selectapproachingtrainer", ()),
    0xD9: ("lockfortrainer", ()),
    0xDA: ("closebraillemessage", ()),
    0xDB: ("messageinstant", (4,)),
    0xDC: ("fadescreenswapbuffers", (1,)),
    0xDD: ("buffertrainerclassname", (1, 2)),
    0xDE: ("buffertrainername", (1, 2)),
    0xDF: ("pokenavcall", (4,)),
    0xE0: ("warpwhitefade", (2, 1, 2, 2)),
    0xE1: ("buffercontestname", (1, 2)),
    0xE2: ("bufferitemnameplural", (1, 2, 2)),
}

SCRIPT_WARP_COMMANDS = COMMON_WARP_COMMANDS | frozenset({0xD1, 0xD7, 0xE0})

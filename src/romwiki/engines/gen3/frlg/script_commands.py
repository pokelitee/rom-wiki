"""FireRed/LeafGreen event-script commands after the shared 0x00-0xC6 range,
from pret/pokefirered's `asm/macros/event.inc` and
`data/script_cmd_table.inc`.
"""

from __future__ import annotations

from romwiki.engines.gen3.shared.scripts import (
    COMMON_SCRIPT_COMMANDS,
    COMMON_WARP_COMMANDS,
)

SCRIPT_COMMANDS: dict[int, tuple[str, tuple[int, ...]]] = {
    **COMMON_SCRIPT_COMMANDS,
    0xC7: ("textcolor", (1,)),
    0xC8: ("loadhelp", (4,)),
    0xC9: ("unloadhelp", ()),
    0xCA: ("signmsg", ()),
    0xCB: ("normalmsg", ()),
    0xCC: ("comparestat", (1, 4)),
    0xCD: ("setmonmodernfatefulencounter", (2,)),
    0xCE: ("checkmonmodernfatefulencounter", (2,)),
    0xCF: ("trywondercardscript", ()),
    0xD0: ("setworldmapflag", (2,)),
    0xD1: ("warpspinenter", (2, 1, 2, 2)),
    0xD2: ("setmonmetlocation", (2, 1)),
    0xD3: ("getbraillestringwidth", (4,)),
    0xD4: ("bufferitemnameplural", (1, 2, 2)),
}

SCRIPT_WARP_COMMANDS = COMMON_WARP_COMMANDS | frozenset({0xD1})

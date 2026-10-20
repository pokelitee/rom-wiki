"""FireRed/LeafGreen event-script commands: the shared 0x00-0xC6 range plus the
commands after it, generated from pret/pokefirered (see
`scripts/pret/gen3_script_commands.py`).
"""

from __future__ import annotations

from romwiki.engines.gen3.shared.script_command_table import (
    COMMON_SCRIPT_COMMANDS,
    FIRERED_SCRIPT_COMMANDS,
)
from romwiki.engines.gen3.shared.scripts import COMMON_WARP_COMMANDS

SCRIPT_COMMANDS = {**COMMON_SCRIPT_COMMANDS, **FIRERED_SCRIPT_COMMANDS}

SCRIPT_WARP_COMMANDS = COMMON_WARP_COMMANDS | frozenset({0xD1})

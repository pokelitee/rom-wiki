from __future__ import annotations

from romwiki.engines.gen4.script_table import (
    Gen4TrainerBattleCommand as Gen4TrainerBattleCommand,
)
from romwiki.engines.gen4.script_table import (
    parse_trainer_battle_commands as _parse_trainer_battle_commands,
)

# Found and verified against the real HeartGold ROM's script archive
# (`a/0/1/2`, 965 files): Platinum's own opcode (0x00E5) found only a single
# plausible site in all of HGSS, far below Platinum's own signal shape (98
# sites across 42 files) -- a strong hint HGSS assigns a different numeric ID
# to the same command, not that HGSS simply lacks these battles.
#
# Scanning every opcode value for the same "valid trainer operand(s) plus a
# real follow-on command" shape and cross-checking hits against the
# already-decoded sight-triggered trainer set turned up 0x00D5: 121 sites
# across 49 files, only 2 of 101 distinct trainer IDs already sight-linked
# (98% new), and the roster is exactly what a real Johto/Kanto script-battle
# roster should look like -- all 8 Johto Gym Leaders in sequence (Falkner,
# Bugsy, Whitney, Morty, Pryce, Jasmine, Chuck, Clair, trainer IDs 20-35),
# Silver the rival across 3 separate story battles, Team Rocket's three
# Executives (Petrel/Archer/Proton), and a wide, non-repeating spread of
# ordinary trainer classes/names -- not the earlier opcode's noise pattern of
# a handful of small IDs clustered on one generic placeholder name.
#
# `CHECK_WON_BATTLE` was found the same way: of every opcode appearing within
# 60 bytes after a confirmed 0x00D5 site, 0x00DC appears at 98% of sites
# (119/121) -- a +7 gap from 0x00D5, mirroring Platinum's own +7 gap between
# 0x00E5 and 0x00EC.
#
# 0x00D5 also independently matches `STARTER_BATTLE_OPCODE` in `hgss/__init__.py`,
# found via an unrelated method (tracing the curated Silver starter-branch
# groups) -- two independent derivations landing on the same value.
START_TRAINER_BATTLE = 0x00D5
CHECK_WON_BATTLE = 0x00DC


def parse_trainer_battle_commands(
    data: bytes, *, trainer_count: int
) -> tuple[Gen4TrainerBattleCommand, ...]:
    """Find literal trainer battles whose operands and follow-on command validate.

    Thin wrapper over the shared scan algorithm in `gen4.script_table` with
    HeartGold/SoulSilver's own opcode. See that function's docstring, and the
    module-level comment above, for the full verification rationale.
    """
    return _parse_trainer_battle_commands(
        data,
        trainer_count=trainer_count,
        start_trainer_battle_opcode=START_TRAINER_BATTLE,
    )

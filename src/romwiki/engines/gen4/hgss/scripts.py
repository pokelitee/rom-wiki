from __future__ import annotations

import struct
from dataclasses import dataclass

from romwiki.engines.gen4.script_table import (
    Gen4TrainerBattleCommand as Gen4TrainerBattleCommand,
)
from romwiki.engines.gen4.script_table import (
    parse_script_table as parse_script_table,
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

# Found via `gen4/hgss/script_opcode_table.py` (the pret/pokeheartgold-derived
# ground-truth opcode table -- see that module's docstring), then verified
# directly against the real HeartGold ROM's script archive: `WildBattle`'s
# real operand is (species, level, flag) -- 5 bytes, one more than DPPT's
# (species, level) -- so its follow-on command sits at offset+7, not
# DPPT's offset+6. Scanning every WildBattle site with a valid species/level
# pair found 19 candidates; 18 validated against a real follow-on command
# (all via the `ClearFlag`-then-`CheckBattleWon` shape DPPT also uses for its
# Legendary/Fateful/Giratina-origin subtypes -- HGSS never observed the
# direct-`CheckBattleWon` shape in this scan, though it's accepted here for
# symmetry with DPPT's own scanner), and the one rejected candidate (a level-2
# Krabby) is exactly the kind of unrelated-byte coincidence the follow-on
# check exists to filter. Every one of the 18 validated sites is a real,
# recognizable HGSS static/legendary encounter: Mewtwo (Cerulean Cave),
# Articuno/Zapdos/Moltres, Suicune (roaming finale), the two Snorlax
# roadblocks (Route 11/12), the two Sudowoodo blocks (Route 36), the Lake of
# Rage red Gyarados, the three Team Rocket self-destructing Electrode
# (Radio Tower), and the Kyogre/Groudon/Rayquaza event trio -- not a single
# implausible species/level pairing among them.
#
# This scan covers only the battle-triggered `WildBattle` convention.
# Direct-to-party gifts (`GiveMon`/`GiveEgg`, e.g. starters, in-game trade
# eggs) use a different, non-battle mechanism and are not covered here.
START_WILD_BATTLE = 0x024D
CLEAR_FLAG = 0x001F


@dataclass(frozen=True, slots=True)
class Gen4StaticEncounterCommand:
    offset: int
    species_id: int
    level: int
    command: str


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


def parse_static_encounter_commands(
    data: bytes, *, species_count: int
) -> tuple[Gen4StaticEncounterCommand, ...]:
    """Find literal `WildBattle` static encounters whose result is validated.

    Species or level operands supplied through script variables are
    intentionally excluded until their control flow can be resolved without
    guessing. See the module-level comment above for the verification
    rationale.
    """
    code_offset = parse_script_table(data)
    commands = []
    signature = struct.pack("<H", START_WILD_BATTLE)

    for offset in range(code_offset, len(data) - 8):
        if data[offset : offset + 2] != signature:
            continue
        species_id, level = struct.unpack_from("<HH", data, offset + 2)
        if not 0 < species_id < species_count or not 0 < level <= 100:
            continue
        if not _has_static_battle_result_check(data, offset):
            continue
        commands.append(
            Gen4StaticEncounterCommand(
                offset=offset,
                species_id=species_id,
                level=level,
                command="WildBattle",
            )
        )
    return tuple(commands)


def _has_static_battle_result_check(data: bytes, offset: int) -> bool:
    # WildBattle's own operand is 5 bytes (species, level, flag), so its
    # follow-on command starts at offset+7 (opcode+operand), not DPPT's
    # offset+6 -- see the module-level comment above.
    if offset + 9 > len(data):
        return False
    following_opcode = struct.unpack_from("<H", data, offset + 7)[0]
    if following_opcode == CHECK_WON_BATTLE:
        return True
    if following_opcode != CLEAR_FLAG:
        return False
    return (
        offset + 13 <= len(data)
        and struct.unpack_from("<H", data, offset + 11)[0] == CHECK_WON_BATTLE
    )

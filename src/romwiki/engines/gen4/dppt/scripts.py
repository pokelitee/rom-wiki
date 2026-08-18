from __future__ import annotations

import struct
from dataclasses import dataclass

from romwiki.engines.gen4.script_table import (
    SCRIPT_COMMAND_COUNT as SCRIPT_COMMAND_COUNT,
)
from romwiki.engines.gen4.script_table import (
    SCRIPT_TABLE_END as SCRIPT_TABLE_END,
)
from romwiki.engines.gen4.script_table import (
    Gen4TrainerBattleCommand as Gen4TrainerBattleCommand,
)
from romwiki.engines.gen4.script_table import (
    parse_script_table as parse_script_table,
)
from romwiki.engines.gen4.script_table import (
    parse_trainer_battle_commands as _parse_trainer_battle_commands,
)

START_TRAINER_BATTLE = 0x00E5
CHECK_WON_BATTLE = 0x00EC
START_WILD_BATTLE = 0x0124
START_LEGENDARY_BATTLE = 0x02BD
START_FATEFUL_ENCOUNTER = 0x0318
START_GIRATINA_ORIGIN_BATTLE = 0x0319
ACTIVATE_ROAMING_POKEMON = 0x021C
CLEAR_FLAG = 0x001F
PLATINUM_ROAMING_SLOT_COUNT = 5
TRAINER_OBJECT_SCRIPT_START = 3000
TRAINER_OBJECT_SCRIPT_END = 3999
TRAINER_OBJECT_ID_OFFSET = 1


@dataclass(frozen=True, slots=True)
class Gen4StaticEncounterCommand:
    offset: int
    species_id: int
    level: int
    command: str


@dataclass(frozen=True, slots=True)
class Gen4RoamingActivationCommand:
    offset: int
    slot: int


def parse_trainer_battle_commands(
    data: bytes, *, trainer_count: int
) -> tuple[Gen4TrainerBattleCommand, ...]:
    """Find literal trainer battles whose operands and follow-on command validate.

    Thin wrapper over the shared scan algorithm in `gen4.script_table` with
    Platinum's own opcode. See that function's docstring for the full
    verification rationale (Elite Four/rival follow-on categories, neighbouring
    opcode selectivity, Renegade Platinum cross-check).
    """
    return _parse_trainer_battle_commands(
        data,
        trainer_count=trainer_count,
        start_trainer_battle_opcode=START_TRAINER_BATTLE,
    )


def parse_static_encounter_commands(
    data: bytes, *, species_count: int
) -> tuple[Gen4StaticEncounterCommand, ...]:
    """Find literal wild battles followed by Platinum's battle-result check.

    Species or level operands supplied through script variables are intentionally
    excluded until their control flow can be resolved without guessing.
    """
    code_offset = parse_script_table(data)
    commands = []
    signatures = {
        START_WILD_BATTLE: "WildBattle",
        START_LEGENDARY_BATTLE: "LegendaryBattle",
        START_FATEFUL_ENCOUNTER: "FatefulEncounter",
        START_GIRATINA_ORIGIN_BATTLE: "GiratinaOriginBattle",
    }

    for offset in range(code_offset, len(data) - 7):
        opcode = struct.unpack_from("<H", data, offset)[0]
        if opcode not in signatures:
            continue
        if not _has_static_battle_result_check(data, offset, opcode):
            continue
        species_id, level = struct.unpack_from("<HH", data, offset + 2)
        if not 0 < species_id < species_count or not 0 < level <= 100:
            continue
        commands.append(
            Gen4StaticEncounterCommand(
                offset=offset,
                species_id=species_id,
                level=level,
                command=signatures[opcode],
            )
        )
    return tuple(commands)


def _has_static_battle_result_check(data: bytes, offset: int, opcode: int) -> bool:
    following_opcode = struct.unpack_from("<H", data, offset + 6)[0]
    if following_opcode == CHECK_WON_BATTLE:
        return True
    if (
        opcode
        not in {
            START_LEGENDARY_BATTLE,
            START_FATEFUL_ENCOUNTER,
            START_GIRATINA_ORIGIN_BATTLE,
        }
        or following_opcode != CLEAR_FLAG
    ):
        return False
    return (
        offset + 12 <= len(data)
        and struct.unpack_from("<H", data, offset + 10)[0] == CHECK_WON_BATTLE
    )


def parse_roaming_activation_commands(
    data: bytes,
) -> tuple[Gen4RoamingActivationCommand, ...]:
    """Find literal Platinum roaming-slot activation commands.

    The command's one-byte operand makes unaligned opcode-like values common in
    other operands. Requiring both a valid Platinum slot and a valid following
    command avoids treating those byte sequences as roaming activations.
    """
    code_offset = parse_script_table(data)
    commands = []
    signature = struct.pack("<H", ACTIVATE_ROAMING_POKEMON)

    for offset in range(code_offset, len(data) - 4):
        if data[offset : offset + 2] != signature:
            continue
        slot = data[offset + 2]
        if slot >= PLATINUM_ROAMING_SLOT_COUNT:
            continue
        following_opcode = struct.unpack_from("<H", data, offset + 3)[0]
        if following_opcode >= SCRIPT_COMMAND_COUNT:
            continue
        commands.append(Gen4RoamingActivationCommand(offset=offset, slot=slot))
    return tuple(commands)

from __future__ import annotations

import struct
from dataclasses import dataclass

from romwiki.util.errors import InvalidRomError

SCRIPT_TABLE_END = 0xFD13
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
_SCRIPT_COMMAND_COUNT = 0x033A


@dataclass(frozen=True, slots=True)
class Gen4TrainerBattleCommand:
    offset: int
    trainer_ids: tuple[int, ...]


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
    """Find literal trainer battles followed by Platinum's win check.

    The two-command sequence distinguishes actual battle invocations from values
    equal to the battle opcode inside operands or embedded script data. Battles
    whose trainer ID is supplied through a script variable are intentionally not
    resolved here.
    """
    code_offset = parse_script_table(data)
    commands = []
    signature = struct.pack("<H", START_TRAINER_BATTLE)
    win_check = struct.pack("<H", CHECK_WON_BATTLE)

    for offset in range(code_offset, len(data) - 7):
        if data[offset : offset + 2] != signature:
            continue
        if data[offset + 6 : offset + 8] != win_check:
            continue
        first_trainer, second_trainer = struct.unpack_from("<HH", data, offset + 2)
        if not 0 < first_trainer < trainer_count:
            continue
        if second_trainer != 0 and not 0 < second_trainer < trainer_count:
            continue
        trainer_ids = (
            (first_trainer, second_trainer) if second_trainer else (first_trainer,)
        )
        commands.append(
            Gen4TrainerBattleCommand(offset=offset, trainer_ids=trainer_ids)
        )
    return tuple(commands)


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
        if following_opcode >= _SCRIPT_COMMAND_COUNT:
            continue
        commands.append(Gen4RoamingActivationCommand(offset=offset, slot=slot))
    return tuple(commands)


def parse_script_table(data: bytes) -> int:
    cursor = 0
    targets = []
    table_end = len(data)
    terminated = False
    while cursor < table_end:
        if cursor + 2 > len(data):
            raise InvalidRomError("Gen IV script table is truncated")
        if struct.unpack_from("<H", data, cursor)[0] == SCRIPT_TABLE_END:
            terminated = True
            break
        if cursor + 4 > table_end:
            raise InvalidRomError("Gen IV script table is truncated")
        relative_offset = struct.unpack_from("<i", data, cursor)[0]
        target = cursor + 4 + relative_offset
        targets.append(target)
        table_end = min(table_end, target)
        cursor += 4

    if not targets:
        raise InvalidRomError("Gen IV script table has no entries")
    if not terminated and cursor != table_end:
        raise InvalidRomError("Gen IV script table does not end at its first script")
    if any(target < table_end or target >= len(data) for target in targets):
        raise InvalidRomError("Gen IV script table contains an invalid entry offset")
    return table_end

from __future__ import annotations

import struct
from collections.abc import Callable
from dataclasses import dataclass

from romwiki.util.errors import InvalidRomError

# Gen V field-script opcodes needed to locate literal trainer-battle triggers.
# Adopted from FrostFalcon/FrostsGen5Editor's `bw1CommandList` (a community,
# actively-maintained BW1 script-command table) and independently cross-
# checked against real Black ROM bytes: walking a known static-encounter
# script (`black-us.toml`'s Magikarp fact, file 526 offset 0x758) from its own
# function-table start lands byte-exact on a `PokePartyAdd` call whose species
# parameter is 129 (Magikarp) at exactly that offset, confirming both this
# opcode's shape and the function-table header format below. `CallTrainerBattle`
# (0x85) is always immediately followed by `TrainerBattleIsVictory` (0x8D)
# reading the same result variable in every real occurrence found in the ROM
# (12/12 samples) -- the same "opcode signature + validating follow-on
# command" pattern this project's `gen4/dppt/scripts.py` already uses for
# Platinum's `StartTrainerBattle`/`CheckWonBattle`, so no full script
# disassembler is needed to find these.
START_TRAINER_BATTLE = 0x0085
START_TRAINER_MULTI_BATTLE = 0x0086
CHECK_TRAINER_BATTLE_WON = 0x008D

# The "always followed by TrainerBattleIsVictory" claim above held for the 12
# samples it was drawn from, but not for the ROM as a whole: 17 of the 130
# sites with valid trainer operands are followed by something else, and those
# are not noise. They are almost entirely the rival battles -- Cheren (53, 54,
# 55, 594), Bianca (59, 60, 61, 494, 495, 595) and N (90) -- trainer records
# that this engine's independently verified Cheren/Bianca/N families already
# contain, which a false positive would not manage. Requiring the win check
# therefore dropped whole battle categories, exactly as the equivalent rule did
# for Platinum in `gen4/dppt/scripts.py`.
#
# Black and Blaze Black agree exactly on this set (130 and 131 sites, the same
# six follow-on commands in the same proportions), so it is verified rather than
# fitted to one ROM. A profile whose scripts use some further follow-on loses
# that link rather than gaining a wrong one, which is the safe direction.
BATTLE_RESULT_COMMANDS = frozenset(
    {CHECK_TRAINER_BATTLE_WON, 0x001E, 0x0019, 0x006C, 0x008E, 0x0028}
)


@dataclass(frozen=True, slots=True)
class Gen5TrainerBattleCommand:
    offset: int
    trainer_ids: tuple[int, ...]


def parse_trainer_battle_commands(
    data: bytes, *, trainer_count: int
) -> tuple[Gen5TrainerBattleCommand, ...]:
    """Find literal `CallTrainerBattle`/`CallTrainerMultiBattle` invocations.

    Battles whose trainer ID is supplied through a script variable (the
    generic sight-triggered-battle convention -- see
    `gen5/bw/overworld.py`) are intentionally not resolved here; only
    literal, in-script trainer IDs are returned, matching this project's
    "decode, don't guess" principle.
    """
    commands = []
    single_signature = struct.pack("<H", START_TRAINER_BATTLE)
    multi_signature = struct.pack("<H", START_TRAINER_MULTI_BATTLE)

    for offset in range(0, len(data) - 9):
        if data[offset : offset + 2] == single_signature:
            follow_on = struct.unpack_from("<H", data, offset + 8)[0]
            if follow_on not in BATTLE_RESULT_COMMANDS:
                continue
            first_trainer, second_trainer, _flags = struct.unpack_from(
                "<HHH", data, offset + 2
            )
            if not 0 < first_trainer < trainer_count:
                continue
            if second_trainer != 0 and not 0 < second_trainer < trainer_count:
                continue
            trainer_ids = (
                (first_trainer, second_trainer) if second_trainer else (first_trainer,)
            )
            commands.append(
                Gen5TrainerBattleCommand(offset=offset, trainer_ids=trainer_ids)
            )
        elif data[offset : offset + 2] == multi_signature:
            if offset + 12 > len(data):
                continue
            follow_on = struct.unpack_from("<H", data, offset + 10)[0]
            if follow_on not in BATTLE_RESULT_COMMANDS:
                continue
            ally, first_trainer, second_trainer, _flags = struct.unpack_from(
                "<HHHH", data, offset + 2
            )
            if not (
                0 < ally < trainer_count
                and 0 < first_trainer < trainer_count
                and 0 < second_trainer < trainer_count
            ):
                continue
            commands.append(
                Gen5TrainerBattleCommand(
                    offset=offset, trainer_ids=(ally, first_trainer, second_trainer)
                )
            )
    return tuple(commands)


# The fossil-revival NPC's script (file 877, `parameters.fossil_revival_script`)
# picks a species by comparing the handed-over item against each real fossil
# item ID, one at a time: `StackPush(itemVar)`, `StackPushConst(item_id)`,
# `StackCmp(==)`, `VMJumpIf`, `WorkSetConst(speciesVar, species_id)` -- a
# fixed 25-byte instruction sequence, found by disassembling the script with
# the same opcode table as trainer battles above (not guessed at): resuming a
# linear walk past the file's short unrecognized preamble (bytes the opcode
# table doesn't cover -- likely a local-variable declaration block specific
# to this script, not investigated further since it isn't needed to find
# this pattern) lands on real, readable code, including a `WorkGet` that
# loads the handed-over item into the compared variable and a `PokePartyAdd`
# that gives the resolved species at level 25. Verified end-to-end against
# both real ROMs
# (Black and White give byte-identical results): items 105/104/101/102/103/
# 100/99/572/573 resolve to species 408/410/138/140/142/347/345/564/566 --
# Skull->Cranidos, Armor->Shieldon, Helix->Omanyte, Dome->Kabuto, Old
# Amber->Aerodactyl, Claw->Anorith, Root->Lileep, Cover->Tirtouga, Plume->
# Archen -- exactly the well-documented, franchise-wide real pairing, now a
# literal decoded ROM fact rather than external game knowledge.
_FOSSIL_ITEM_VAR = 32802
_FOSSIL_SPECIES_VAR = 32803
FOSSIL_SPECIES_VARIABLE = _FOSSIL_SPECIES_VAR
_STACK_PUSH = 0x9
_STACK_PUSH_CONST = 0x8
_STACK_CMP = 0x11
_STACK_CMP_EQUAL = 1
_VM_JUMP_IF = 0x1F
_WORK_SET_CONST = 0x28
_FOSSIL_PATTERN_LENGTH = 25


@dataclass(frozen=True, slots=True)
class Gen5FossilRevival:
    item_id: int
    species_id: int


def parse_fossil_revival_table(data: bytes) -> tuple[Gen5FossilRevival, ...]:
    """Find literal fossil-item-to-species comparisons in the revival script.

    See the module comment above for the exact instruction pattern and how
    it was found and verified.
    """
    revivals = []
    for offset in range(0, len(data) - _FOSSIL_PATTERN_LENGTH + 1):
        if struct.unpack_from("<H", data, offset)[0] != _STACK_PUSH:
            continue
        if struct.unpack_from("<H", data, offset + 2)[0] != _FOSSIL_ITEM_VAR:
            continue
        if struct.unpack_from("<H", data, offset + 4)[0] != _STACK_PUSH_CONST:
            continue
        item_id = struct.unpack_from("<H", data, offset + 6)[0]
        if struct.unpack_from("<H", data, offset + 8)[0] != _STACK_CMP:
            continue
        if struct.unpack_from("<H", data, offset + 10)[0] != _STACK_CMP_EQUAL:
            continue
        if struct.unpack_from("<H", data, offset + 12)[0] != _VM_JUMP_IF:
            continue
        if struct.unpack_from("<H", data, offset + 19)[0] != _WORK_SET_CONST:
            continue
        if struct.unpack_from("<H", data, offset + 21)[0] != _FOSSIL_SPECIES_VAR:
            continue
        species_id = struct.unpack_from("<H", data, offset + 23)[0]
        revivals.append(Gen5FossilRevival(item_id=item_id, species_id=species_id))
    return tuple(revivals)


def find_fossil_revival_script(
    read_script_member: Callable[[int], bytes],
    *,
    member_count: int,
    item_count: int,
    species_count: int,
) -> tuple[int, tuple[Gen5FossilRevival, ...]]:
    """Locate the one script containing a complete, valid fossil mapping."""
    candidates = []
    for member in range(member_count):
        revivals = parse_fossil_revival_table(read_script_member(member))
        if len(revivals) < 2 or any(
            not 0 < revival.item_id < item_count
            or not 0 < revival.species_id < species_count
            for revival in revivals
        ):
            continue
        candidates.append((member, revivals))
    if len(candidates) != 1:
        raise InvalidRomError(
            f"Expected exactly one fossil revival script, found {len(candidates)}"
        )
    return candidates[0]

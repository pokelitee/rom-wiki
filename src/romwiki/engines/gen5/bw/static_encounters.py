from __future__ import annotations

from collections.abc import Callable

from romwiki.engines.gen5.script_disassembler import (
    Gen5Instruction,
    disassemble_script,
)
from romwiki.schema import RecordProvenance, StaticEncounter
from romwiki.util.errors import InvalidRomError

from .scripts import FOSSIL_SPECIES_VARIABLE, find_fossil_revival_script


def discover_static_encounters(
    read_script_member: Callable[[int], bytes],
    *,
    member_count: int,
    archive_path: str,
    species_count: int,
    item_count: int,
) -> tuple[StaticEncounter, ...]:
    """Discover literal BW gifts and scripted battles from reachable bytecode."""
    discovered: list[tuple[tuple[int, int | None, bool], int, Gen5Instruction]] = []
    first_member_by_fact: dict[tuple[int, int | None, bool], int] = {}
    for member in range(member_count):
        for instruction in disassemble_script(read_script_member(member)):
            fact = _static_fact(instruction, species_count=species_count)
            if fact is None:
                continue
            first_member = first_member_by_fact.setdefault(fact, member)
            if first_member == member:
                discovered.append((fact, member, instruction))

    fossil_member, fossil_revivals = find_fossil_revival_script(
        read_script_member,
        member_count=member_count,
        item_count=item_count,
        species_count=species_count,
    )
    fossil_commands = [
        instruction
        for instruction in disassemble_script(read_script_member(fossil_member))
        if instruction.name == "PokePartyAdd"
        and instruction.params[1] == FOSSIL_SPECIES_VARIABLE
        and 0 < instruction.params[3] <= 100
    ]
    if len(fossil_commands) != 1:
        raise InvalidRomError(
            "Expected exactly one fossil party-add command, "
            f"found {len(fossil_commands)}"
        )
    fossil_command = fossil_commands[0]
    for revival in fossil_revivals:
        discovered.append(
            (
                (revival.species_id, fossil_command.params[3], False),
                fossil_member,
                fossil_command,
            )
        )

    return tuple(
        StaticEncounter(
            encounter_id=encounter_id,
            species_id=species_id,
            level=level,
            is_egg=is_egg,
            provenance=RecordProvenance(
                source="rom", archive=archive_path, member=member
            ),
            command_offset=instruction.offset,
            command=instruction.name,
        )
        for encounter_id, (
            (species_id, level, is_egg),
            member,
            instruction,
        ) in enumerate(discovered)
    )


def _static_fact(
    instruction: Gen5Instruction, *, species_count: int
) -> tuple[int, int | None, bool] | None:
    if instruction.name == "CallWildBattle":
        species_id, level, _result = instruction.params
        is_egg = False
    elif instruction.name in {"PokePartyAdd", "PokePartyAddEx"}:
        species_id = instruction.params[1]
        level = instruction.params[3]
        is_egg = False
    elif instruction.name == "PokePartyAddEgg":
        species_id = instruction.params[1]
        level = None
        is_egg = True
    else:
        return None
    if not 0 < species_id < species_count:
        return None
    if level is not None and not 0 < level <= 100:
        return None
    return species_id, level, is_egg

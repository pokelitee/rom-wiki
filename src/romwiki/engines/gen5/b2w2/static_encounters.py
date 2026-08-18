from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from romwiki.schema import RecordProvenance, StaticEncounter
from romwiki.util.errors import InvalidRomError

from .disassembler import Gen5Instruction, disassemble_script

_FOSSIL_ITEM_VARIABLE = 32802
_FOSSIL_SPECIES_VARIABLE = 32803

# Kyurem's story-battle fusions with N's Reshiram/Zekrom -- the only
# `CallWildBattleEx` calls that are genuinely uncatchable. Every other
# non-zero form seen in this opcode (e.g. Therian Forme Tornadus/Thundurus,
# Zen Mode Darmanitan) is a real, catchable/battleable encounter and must
# not be excluded by a blanket form check.
_KYUREM_SPECIES_ID = 646
_UNCATCHABLE_STORY_FORMS = frozenset({(_KYUREM_SPECIES_ID, 1), (_KYUREM_SPECIES_ID, 2)})


@dataclass(frozen=True, slots=True)
class Gen5FossilRevival:
    item_id: int
    species_id: int


def find_fossil_revival_script(
    read_script_member: Callable[[int], bytes],
    *,
    member_count: int,
    species_count: int,
    item_count: int,
) -> tuple[int, tuple[Gen5FossilRevival, ...]]:
    instructions_by_member = {
        member: disassemble_script(read_script_member(member))
        for member in range(member_count)
    }
    candidates = _fossil_candidates(
        instructions_by_member,
        species_count=species_count,
        item_count=item_count,
    )
    if len(candidates) != 1:
        raise InvalidRomError(
            f"Expected exactly one B2W2 fossil revival script, found {len(candidates)}"
        )
    member, _party_add, mappings = candidates[0]
    return member, tuple(
        Gen5FossilRevival(item_id=item_id, species_id=species_id)
        for item_id, species_id in mappings
    )


def discover_static_encounters(
    read_script_member: Callable[[int], bytes],
    *,
    member_count: int,
    archive_path: str,
    species_count: int,
    item_count: int,
) -> tuple[StaticEncounter, ...]:
    """Discover B2W2 gifts and catchable scripted wild encounters.

    Legendary rematch levels are alternate paths to the same one-time
    encounter, so the earliest (lowest-level) literal is retained. Exact
    duplicate gift paths are collapsed, while different species or gift facts
    remain distinct. Form-specific Kyurem story battles are not catchable and
    are excluded; the form-zero shiny Haxorus command is catchable.
    """
    data_by_member = {
        member: read_script_member(member) for member in range(member_count)
    }
    instructions_by_member = {
        member: disassemble_script(data) for member, data in data_by_member.items()
    }

    wild: list[tuple[tuple[int, int | None, bool], int, Gen5Instruction]] = []
    gifts: list[tuple[tuple[int, int | None, bool], int, Gen5Instruction]] = []
    for member, instructions in instructions_by_member.items():
        for instruction in instructions:
            fact = _static_fact(instruction, species_count=species_count)
            if fact is None:
                continue
            species_id, level, is_egg = fact
            if instruction.name in {"CallWildBattle", "CallWildBattleEx"}:
                assert level is not None
                wild.append((fact, member, instruction))
            else:
                gifts.append((fact, member, instruction))

    discovered = _deduplicate_wild_paths(wild)
    discovered.extend(_deduplicate_exact_paths(gifts))
    discovered.extend(
        _discover_fossils(
            instructions_by_member,
            species_count=species_count,
            item_count=item_count,
        )
    )
    discovered.sort(key=lambda value: (value[1], value[2].offset, value[0]))

    return tuple(
        StaticEncounter(
            encounter_id=encounter_id,
            species_id=fact[0],
            level=fact[1],
            is_egg=fact[2],
            provenance=RecordProvenance(
                source="rom", archive=archive_path, member=member
            ),
            command_offset=instruction.offset,
            command=instruction.name,
        )
        for encounter_id, (fact, member, instruction) in enumerate(discovered)
    )


def _deduplicate_wild_paths(
    candidates: list[tuple[tuple[int, int | None, bool], int, Gen5Instruction]],
) -> list[tuple[tuple[int, int | None, bool], int, Gen5Instruction]]:
    """Collapse lifecycle alternatives without losing distinct encounters."""
    by_species_and_member: dict[
        tuple[int, int], list[tuple[tuple[int, int | None, bool], int, Gen5Instruction]]
    ] = {}
    for candidate in candidates:
        by_species_and_member.setdefault((candidate[0][0], candidate[1]), []).append(
            candidate
        )

    initial_paths = []
    for paths in by_species_and_member.values():
        # A one-time legendary can have initial and postgame levels in the same
        # script. They are mutually exclusive lifecycle paths, not two catches.
        initial_paths.append(min(paths, key=lambda value: value[0][1] or 0))
    return _deduplicate_exact_paths(initial_paths)


def _deduplicate_exact_paths(
    candidates: list[tuple[tuple[int, int | None, bool], int, Gen5Instruction]],
) -> list[tuple[tuple[int, int | None, bool], int, Gen5Instruction]]:
    kept = []
    seen_member_facts: set[tuple[tuple[int, int | None, bool], int]] = set()
    seen_command_paths: set[
        tuple[tuple[int, int | None, bool], int, str, tuple[int, ...]]
    ] = set()
    for candidate in candidates:
        fact, member, instruction = candidate
        member_fact = fact, member
        command_path = fact, instruction.offset, instruction.name, instruction.params
        if (
            member_fact not in seen_member_facts
            and command_path not in seen_command_paths
        ):
            kept.append(candidate)
            seen_member_facts.add(member_fact)
            seen_command_paths.add(command_path)
    return kept


def _static_fact(
    instruction: Gen5Instruction, *, species_count: int
) -> tuple[int, int | None, bool] | None:
    if instruction.name == "CallWildBattle":
        species_id, level, _result = instruction.params
        is_egg = False
    elif instruction.name == "CallWildBattleEx":
        species_id, level, form, _result = instruction.params
        if (species_id, form) in _UNCATCHABLE_STORY_FORMS:
            return None
        is_egg = False
    elif instruction.name in {"PokePartyAdd", "PokePartyAddEx"}:
        species_id = instruction.params[1]
        level = instruction.params[3]
        is_egg = False
    elif instruction.name == "PokePartyAddN":
        _destination, species_id, level, *_attributes = instruction.params
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


def _discover_fossils(
    instructions_by_member: dict[int, tuple[Gen5Instruction, ...]],
    *,
    species_count: int,
    item_count: int,
) -> list[tuple[tuple[int, int, bool], int, Gen5Instruction]]:
    candidates = _fossil_candidates(
        instructions_by_member,
        species_count=species_count,
        item_count=item_count,
    )
    if len(candidates) != 1:
        raise InvalidRomError(
            f"Expected exactly one B2W2 fossil revival script, found {len(candidates)}"
        )
    member, party_add, mappings = candidates[0]
    return [
        ((species_id, party_add.params[3], False), member, party_add)
        for _item_id, species_id in mappings
    ]


def _fossil_candidates(
    instructions_by_member: dict[int, tuple[Gen5Instruction, ...]],
    *,
    species_count: int,
    item_count: int,
) -> list[tuple[int, Gen5Instruction, list[tuple[int, int]]]]:
    candidates = []
    for member, instructions in instructions_by_member.items():
        party_adds = [
            instruction
            for instruction in instructions
            if instruction.name == "PokePartyAdd"
            and instruction.params[1] == _FOSSIL_SPECIES_VARIABLE
            and 0 < instruction.params[3] <= 100
        ]
        mappings = _fossil_mappings(instructions, species_count, item_count)
        if len(mappings) >= 2 and len(party_adds) == 1:
            candidates.append((member, party_adds[0], mappings))
    return candidates


def _fossil_mappings(
    instructions: tuple[Gen5Instruction, ...], species_count: int, item_count: int
) -> list[tuple[int, int]]:
    mappings = []
    for index in range(len(instructions) - 4):
        push_item_var, push_item, compare, jump, set_species = instructions[
            index : index + 5
        ]
        if not (
            push_item_var.name == "StackPush"
            and push_item_var.params == (_FOSSIL_ITEM_VARIABLE,)
            and push_item.name == "StackPushConst"
            and compare.name == "StackCmp"
            and compare.params == (1,)
            and jump.name == "VMJumpIf"
            and set_species.name == "WorkSetConst"
            and set_species.params[0] == _FOSSIL_SPECIES_VARIABLE
            and push_item_var.next_offset == push_item.offset
            and push_item.next_offset == compare.offset
            and compare.next_offset == jump.offset
            and jump.next_offset == set_species.offset
        ):
            continue
        item_id = push_item.params[0]
        species_id = set_species.params[1]
        if 0 < item_id < item_count and 0 < species_id < species_count:
            mappings.append((item_id, species_id))
    return mappings


__all__ = ["discover_static_encounters", "find_fossil_revival_script"]

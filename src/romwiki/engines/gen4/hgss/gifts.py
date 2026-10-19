from __future__ import annotations

from dataclasses import dataclass

from romwiki.engines.gen4.hgss.script_opcode_table import OPCODE_TABLE
from romwiki.engines.gen4.shared.script_disassembler import (
    Gen4Instruction,
    disassemble_function,
)
from romwiki.engines.gen4.shared.script_table import parse_script_function_offsets

# HGSS's own `GiveMon` opcode (0x0089, per `gen4/hgss/script_opcode_table.py`)
# takes six 2-byte operands -- structurally different from Platinum's simpler
# four-operand (species, level, held_item, output_variable) shape, per
# pret/pokeheartgold's own arg list (`['species', 'var', 'var', 'var', 'var',
# 'var']`). The three middle operands (params[2:5]) are not decoded -- every
# confirmed hit has them at 0 except Giratina's (112, 1, 26), so their real
# meaning (held item? form? origin flag?) isn't established from this sample
# alone, and this project does not publish a guessed field. Only species and
# level are extracted.
#
# Validated with a control-flow-aware disassembler (`disassemble_function`,
# HGSS's own opcode table) starting from every real function offset in the
# script archive, not a raw byte scan: only `GiveMon`/`GiveEgg` instructions
# actually reachable from real code are candidates, then species/level bounds
# filter out the remainder. This combination was verified directly against
# all four real gen4_hgss ROMs (HeartGold, SoulSilver, Sacred Gold, Storm
# Silver): a pure reachable-but-unfiltered scan still surfaces `GiveMon` sites
# whose species operand is a script variable (>= 0x8000, e.g. weekly Bug
# Catching Contest prizes), which the species/level bounds check correctly
# rejects, while every literal-species hit that passes both checks is a real,
# independently-recognizable gift: HeartGold/SoulSilver -- Tyrogue Lv10
# (Saffron's Fighting Dojo), Dratini Lv15 (the Dragon's Den), Dialga/Palkia/
# Giratina all Lv1 (the Sinjoh Ruins post-Arceus trio), Eevee Lv5 (Bill's
# grandson in Goldenrod), and one Lv15 Tentacool; Sacred Gold/Storm Silver
# additionally surface their own hack-added roster (e.g. Manaphy/Phione-range
# species IDs 489/490, consistent with those hacks' documented Sinnoh-era
# additions).
#
# `GiveEgg(species, var)` (opcode 0x008A) -- verified reachable-and-bounded
# hits are identical across HeartGold and SoulSilver (script member 860, a shared common
# script): three literal egg choices, species 179/194/218 (Mareep/Wooper/
# Slugma), each one immediately preceded in the disassembly by a
# `BufferSpeciesName(1, species, 0, 0)` call buffering that exact same
# species into the message about to be shown -- a real validating pattern,
# the same role `CheckBattleWon` plays for `WildBattle`. Sacred Gold/Storm
# Silver reuse the same three IDs plus their own hack-added egg choices
# (species 447/489/490), all equally validated by reachability, bounds, and
# the same preceding `BufferSpeciesName` pattern.
#
# `GiveTogepiEgg` (opcode 0x0308) takes no operands at all -- species
# identity is fixed by the routine itself, not by any per-call operand, so there is no literal
# value to bounds-check the way `GiveMon`/`GiveEgg` allow. The opcode's own
# name comes from the same pret/pokeheartgold-derived table already trusted
# for every other opcode in this codebase (including `GiveMon`/`GiveEgg`
# themselves); species identity here rests on that same trust, resolved
# dynamically against the current profile's own decoded Pokémon name table
# (never a hardcoded species ID) so a hack that renumbers species is not
# silently mislabeled. Verified reachable in all four real gen4_hgss ROMs:
# one real site in HeartGold/SoulSilver (script member 858, guarded by a
# `GetPartyCount`/`CompareVarToValue(_, 6)` party-space check), two in Sacred
# Gold/Storm Silver.


@dataclass(frozen=True, slots=True)
class Gen4HgssPokemonGiftCommand:
    offset: int
    species_id: int
    level: int


@dataclass(frozen=True, slots=True)
class Gen4HgssEggGiftCommand:
    offset: int
    species_id: int


@dataclass(frozen=True, slots=True)
class Gen4HgssTogepiEggGiftCommand:
    offset: int


def _reachable_instructions(data: bytes) -> dict[int, Gen4Instruction]:
    instructions: dict[int, Gen4Instruction] = {}
    for start in parse_script_function_offsets(data):
        instructions.update(
            disassemble_function(data, start, opcode_table=OPCODE_TABLE)
        )
    return instructions


def parse_pokemon_gift_commands(
    data: bytes, *, species_count: int
) -> tuple[Gen4HgssPokemonGiftCommand, ...]:
    """Find real, reachable `GiveMon` gifts whose species and level validate.

    See the module-level comment above for the verification rationale and
    what this deliberately does not decode.
    """
    commands = []
    for offset, instruction in sorted(_reachable_instructions(data).items()):
        if instruction.name != "GiveMon":
            continue
        species_id, level, _p2, _p3, _p4, output_variable = instruction.params
        if not 0 < species_id < species_count or not 0 < level <= 100:
            continue
        if output_variable < 0x8000:
            continue
        commands.append(
            Gen4HgssPokemonGiftCommand(
                offset=offset, species_id=species_id, level=level
            )
        )
    return tuple(commands)


def parse_egg_gift_commands(
    data: bytes, *, species_count: int
) -> tuple[Gen4HgssEggGiftCommand, ...]:
    """Find real, reachable `GiveEgg` gifts whose species validates.

    See the module-level comment above for the verification rationale.
    """
    commands = []
    for offset, instruction in sorted(_reachable_instructions(data).items()):
        if instruction.name != "GiveEgg":
            continue
        species_id, _output_variable = instruction.params
        if not 0 < species_id < species_count:
            continue
        commands.append(Gen4HgssEggGiftCommand(offset=offset, species_id=species_id))
    return tuple(commands)


def parse_togepi_egg_gift_commands(
    data: bytes,
) -> tuple[Gen4HgssTogepiEggGiftCommand, ...]:
    """Find real, reachable `GiveTogepiEgg` sites.

    See the module-level comment above: this opcode carries no species
    operand, so species identity is resolved by the caller from the opcode's
    own name against the current profile's decoded Pokémon name table.
    """
    return tuple(
        Gen4HgssTogepiEggGiftCommand(offset=offset)
        for offset, instruction in sorted(_reachable_instructions(data).items())
        if instruction.name == "GiveTogepiEgg"
    )

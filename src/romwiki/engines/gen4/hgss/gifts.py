from __future__ import annotations

import struct
from dataclasses import dataclass

from romwiki.engines.gen4.script_table import parse_script_table

# HGSS's own `GiveMon` opcode (0x0089, per `gen4/hgss/script_opcode_table.py`)
# takes six 2-byte operands -- structurally different from Platinum's simpler
# four-operand (species, level, held_item, output_variable) shape, per
# pret/pokeheartgold's own arg list (`['species', 'var', 'var', 'var', 'var',
# 'var']`). Verified directly against the real HeartGold ROM's script
# archive: filtering for a valid species, a valid level (params[1]) in
# 1-100, and a real script-variable output slot (params[5] >= 0x8000, the
# same variable-ID boundary DPPT's own scanner and HGSS's trainer-battle
# scanner both use) finds exactly seven real, independently-recognizable
# gifts and nothing else: Tyrogue Lv10 (Saffron City's Fighting Dojo),
# Dratini Lv15 (the Dragon's Den), Dialga/Palkia/Giratina all Lv1 (the
# Sinjoh Ruins post-Arceus event trio -- genuinely obtained at level 1, a
# real, well-known fact about that specific event), Eevee Lv5 (Bill's
# grandson in Goldenrod), and one Lv15 Tentacool of unconfirmed provenance
# but the identical byte shape as every confirmed hit.
#
# The three middle operands (params[2:5]) are not decoded -- every confirmed
# hit above has them at 0 except Giratina's (112, 1, 26), so their real
# meaning (held item? form? origin flag?) isn't established from this sample
# alone, and this project does not publish a guessed field. Only species and
# level are extracted.
GIVE_POKEMON_COMMAND = 0x0089
_OUTPUT_VARIABLE_MINIMUM = 0x8000


@dataclass(frozen=True, slots=True)
class Gen4HgssPokemonGiftCommand:
    offset: int
    species_id: int
    level: int


def parse_pokemon_gift_commands(
    data: bytes, *, species_count: int
) -> tuple[Gen4HgssPokemonGiftCommand, ...]:
    """Find literal `GiveMon` gifts whose species, level, and output slot validate.

    See the module-level comment above for the verification rationale and
    what this deliberately does not decode.
    """
    code_offset = parse_script_table(data)
    commands = []
    signature = struct.pack("<H", GIVE_POKEMON_COMMAND)

    for offset in range(code_offset, len(data) - 14):
        if data[offset : offset + 2] != signature:
            continue
        species_id, level, _p2, _p3, _p4, output_variable = struct.unpack_from(
            "<6H", data, offset + 2
        )
        if not 0 < species_id < species_count or not 0 < level <= 100:
            continue
        if output_variable < _OUTPUT_VARIABLE_MINIMUM:
            continue
        commands.append(
            Gen4HgssPokemonGiftCommand(
                offset=offset, species_id=species_id, level=level
            )
        )
    return tuple(commands)

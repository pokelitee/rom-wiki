from __future__ import annotations

from dataclasses import dataclass
import struct

from romwiki.engines.gen4_dppt.scripts import _parse_script_table
from romwiki.util.errors import InvalidRomError


GIVE_POKEMON_COMMAND = 0x0096
GIVE_EGG_COMMAND = 0x0097


@dataclass(frozen=True, slots=True)
class Gen4PokemonGiftCommand:
    offset: int
    species_id: int
    level: int
    held_item_id: int


@dataclass(frozen=True, slots=True)
class Gen4EggGiftCommand:
    offset: int
    species_id: int


def parse_pokemon_gift_commands(
    data: bytes, *, species_count: int, item_count: int
) -> tuple[Gen4PokemonGiftCommand, ...]:
    code_offset = _parse_script_table(data)
    commands = []
    for offset in range(code_offset, len(data) - 9):
        opcode, species_id, level, held_item_id, output_variable = (
            struct.unpack_from("<5H", data, offset)
        )
        if opcode != GIVE_POKEMON_COMMAND:
            continue
        if not 0 < species_id < species_count or not 0 < level <= 100:
            continue
        if not 0 <= held_item_id < item_count or output_variable < 0x4000:
            continue
        commands.append(
            Gen4PokemonGiftCommand(
                offset=offset,
                species_id=species_id,
                level=level,
                held_item_id=held_item_id,
            )
        )
    return tuple(commands)


def parse_egg_gift_command(
    data: bytes, *, offset: int, species_count: int
) -> Gen4EggGiftCommand:
    if offset < 0 or offset + 6 > len(data):
        raise InvalidRomError("Gen IV egg gift command is out of bounds")
    opcode, species_id, _unused = struct.unpack_from("<3H", data, offset)
    if opcode != GIVE_EGG_COMMAND:
        raise InvalidRomError(
            f"Expected egg gift command at 0x{offset:X}, found 0x{opcode:04X}"
        )
    if not 0 < species_id < species_count:
        raise InvalidRomError(f"Egg gift references invalid species {species_id}")
    return Gen4EggGiftCommand(offset=offset, species_id=species_id)

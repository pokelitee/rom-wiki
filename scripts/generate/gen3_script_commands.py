"""Generate Generation III event-script command tables from pret.

Each primitive command macro in `asm/macros/event.inc` is `.byte <opcode>`
followed by fixed-width operand directives, and `data/script_cmd_table.inc`
orders the handlers by opcode. Helper macros expand to fixed sizes (`map`
is group and number, `stringvar` one byte, `formatwarp` map + warp ID + x +
y). A `waitstate` or `waitmovement` inside a macro is a separate command,
and `trainerbattle`'s pointers depend on its battle type, so its table entry
lists only the fixed type, trainer, and local ID.

FireRed/LeafGreen and Emerald share opcodes 0x00-0xC6; each game's later
commands go in its own table. Run from the repository root:

    python scripts/generate/gen3_script_commands.py [--check]
"""

from __future__ import annotations

import argparse
import json
import re

from common import ROOT, check_or_write
from decomp_sources import pinned, read

OUTPUT = ROOT / "src/romwiki/engines/gen3/shared/script_command_table.py"
SHARED_LAST_OPCODE = 0xC6
TRAINER_BATTLE = 0x5C
_SIZES = {".byte": 1, ".2byte": 2, ".4byte": 4}
_HELPERS = {"map": [2], "stringvar": [1], "formatwarp": [2, 1, 2, 2]}
_SEPARATE_COMMANDS = {"waitstate", "waitmovement"}
_GAMES = {"firered": "pokefirered", "emerald": "pokeemerald"}


def _handlers(project: str) -> dict[int, str]:
    """`opcode -> handler name` from `data/script_cmd_table.inc`."""
    handlers = {}
    for line in read(project, "data/script_cmd_table.inc").splitlines():
        match = re.search(
            r"(?:\.4byte|script_cmd_table_entry\s+\w+)\s+ScrCmd_(\w+)\s+@\s+0x([0-9a-fA-F]+)",
            line,
        )
        if match:
            handlers[int(match.group(2), 16)] = match.group(1)
    return handlers


def _opcode_constants(project: str) -> dict[str, int]:
    """Emerald names opcodes `SCR_OP_*` in its command table."""
    constants = {}
    for line in read(project, "data/script_cmd_table.inc").splitlines():
        match = re.search(
            r"script_cmd_table_entry\s+(SCR_OP_\w+)\s+\w+\s+@\s+0x([0-9a-fA-F]+)", line
        )
        if match:
            constants[match.group(1)] = int(match.group(2), 16)
    return constants


def _operand_widths(project: str) -> dict[int, set[tuple[int, ...]]]:
    """Every operand layout the macros emit after each opcode."""
    constants = _opcode_constants(project)
    text = read(project, "asm/macros/event.inc")
    layouts: dict[int, set[tuple[int, ...]]] = {}
    for match in re.finditer(r"\.macro\s+\w+[^\n]*\n(.*?)\n\s*\.endm", text, re.S):
        current: tuple[int, list[int]] | None = None
        for raw in match.group(1).splitlines():
            line = raw.split("@")[0].strip()
            if not line:
                continue
            word = line.split()[0]
            opcode = re.match(r"\.byte\s+(SCR_OP_\w+|0x[0-9a-fA-F]+)$", line)
            if opcode:
                if current is not None:
                    layouts.setdefault(current[0], set()).add(tuple(current[1]))
                token = opcode.group(1)
                value = (
                    constants[token] if token.startswith("SCR_OP_") else int(token, 16)
                )
                current = (value, [])
                continue
            if current is None:
                continue
            if word.startswith(".if") or word in (".else", ".elseif", ".endif"):
                layouts.setdefault(current[0], set()).add(tuple(current[1]))
                current = None
            elif word in _SIZES:
                current[1].append(_SIZES[word])
            elif word in _HELPERS:
                current[1].extend(_HELPERS[word])
            elif word not in _SEPARATE_COMMANDS:
                raise SystemExit(f"{project}: unexpected operand line {line!r}")
        if current is not None:
            layouts.setdefault(current[0], set()).add(tuple(current[1]))
    return layouts


def _table(project: str) -> dict[int, tuple[str, tuple[int, ...]]]:
    widths = _operand_widths(project)
    table: dict[int, tuple[str, tuple[int, ...]]] = {}
    for opcode, handler in sorted(_handlers(project).items()):
        if opcode == TRAINER_BATTLE:
            table[opcode] = (handler, (1, 2, 2))
            continue
        # A macro that only emits the opcode before branching contributes an
        # empty layout; any other layout must agree in total size.
        layouts = {layout for layout in widths.get(opcode, set()) if layout} or {()}
        if len({sum(layout) for layout in layouts}) != 1:
            raise SystemExit(f"{project}: opcode {opcode:#x} has layouts {layouts}")
        table[opcode] = (handler, max(layouts, key=len))
    return table


def _entries(table: dict[int, tuple[str, tuple[int, ...]]]) -> str:
    return "".join(
        f"    0x{opcode:02X}: ({json.dumps(name)}, {widths!r}),\n"
        for opcode, (name, widths) in sorted(table.items())
    )


def generate() -> str:
    tables = {game: _table(project) for game, project in _GAMES.items()}
    shared = {
        opcode: entry
        for opcode, entry in tables["firered"].items()
        if opcode <= SHARED_LAST_OPCODE
    }
    for opcode, (_, widths) in shared.items():
        if sum(tables["emerald"][opcode][1]) != sum(widths):
            raise SystemExit(f"Opcode {opcode:#x} differs between the games")
    commits = ", ".join(
        f"{pinned(project)[0]}@{pinned(project)[1][:12]}" for project in _GAMES.values()
    )
    tails = "".join(
        f"\n{game.upper()}_SCRIPT_COMMANDS: dict[int, tuple[str, tuple[int, ...]]] = {{\n"
        + _entries({k: v for k, v in table.items() if k > SHARED_LAST_OPCODE})
        + "}\n"
        for game, table in tables.items()
    )
    return (
        '"""Generation III event-script commands: opcode -> (name, operand widths).\n\n'
        f"Generated by scripts/generate/gen3_script_commands.py from {commits}.\n"
        'Do not edit by hand.\n"""\n\n'
        "from __future__ import annotations\n\n"
        "COMMON_SCRIPT_COMMANDS: dict[int, tuple[str, tuple[int, ...]]] = {\n"
        + _entries(shared)
        + "}\n"
        + tails
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if out of date")
    args = parser.parse_args()
    check_or_write({OUTPUT: generate()}, check=args.check)


if __name__ == "__main__":
    main()

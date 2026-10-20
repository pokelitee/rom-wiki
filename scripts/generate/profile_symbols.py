"""Generate the pret symbol subsets that profiles resolve addresses from.

For each retail profile, `profiles/symbols/<profile>.toml` lists the symbols
the profiles name (`<parameter>_symbol = "<symbol>"`) with their offset and
size, plus the `gSpecials` index of each special the profiles name
(`<parameter>_special = "<handler>"`). Only what profiles use is kept, so the
files stay small and readable.

GBA offsets are from the start of the ROM. Each GBA symbol also records its
`address` and the `pointers` to it: every 4-byte-aligned offset in the retail
ROM that holds that address, mostly code literal pools. A hack that moves a
table repoints those words, so reading them in the hack finds the table.
Finding them needs the retail ROMs, located through `.local/games.toml` and
checked against their profile hashes.

Platinum's offsets come from its linker map and are relative to ARM9 or, with
`overlay`, to that overlay's load address, matching how DS profiles already
locate tables. Run from the repository root:

    python scripts/generate/profile_symbols.py [--check]
"""

from __future__ import annotations

import argparse
import hashlib
import re
import struct
import tomllib
from typing import Any

from common import GAMES_CONFIG, ROOT, check_or_write, local_config, local_path
from pret_sources import pinned, read

PROFILES = ROOT / "profiles"
OUTPUT = PROFILES / "symbols"
GBA_ROM_BASE = 0x08000000
ARM9_LOAD_ADDRESS = 0x02000000
# Symbol table -> (pret project, symbol file on its symbols branch).
TABLES = {
    "firered-us": ("pokefirered", "pokefirered.sym"),
    "leafgreen-us": ("pokefirered", "pokeleafgreen.sym"),
    "emerald-us": ("pokeemerald", "pokeemerald.sym"),
    "platinum-us": ("pokeplatinum", "platinumus.xMAP"),
}
_SPECIALS_PATH = "data/specials.inc"


def _profiles() -> dict[str, dict[str, Any]]:
    profiles = {}
    for path in sorted(PROFILES.rglob("*.toml")):
        if OUTPUT not in path.parents:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
            profiles[data["profile"]["id"]] = data
    return profiles


def _profile_references(
    profiles: dict[str, dict[str, Any]],
) -> dict[str, tuple[set[str], set[str]]]:
    """`table -> (symbols, specials)` named by the profiles that use it,
    including names a profile inherits through `extends`.
    """

    def lineage(profile_id: str) -> list[dict]:
        chain = []
        while profile_id is not None:
            data = profiles[profile_id]
            chain.append(data)
            profile_id = data["profile"].get("extends")
        return chain

    references: dict[str, tuple[set[str], set[str]]] = {}
    for profile_id in profiles:
        chain = lineage(profile_id)
        table = next(
            (
                data["profile"]["symbols"]
                for data in chain
                if "symbols" in data["profile"]
            ),
            None,
        )
        if table is None:
            continue
        symbols, specials = references.setdefault(table, (set(), set()))
        for data in chain:
            for key, value in data.get("parameters", {}).items():
                if key.endswith("_symbol"):
                    symbols.add(value)
                elif key.endswith("_special") and isinstance(value, str):
                    specials.add(value)
    return references


# `name -> (offset, size, overlay ID or None)`.
_Symbols = dict[str, tuple[int, int, int | None]]


def _gba_symbols(text: str) -> _Symbols:
    """Symbols from a GNU `.sym` file: `address type size name`."""
    found: _Symbols = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 4 and parts[1] in ("g", "l"):
            offset = int(parts[0], 16) - GBA_ROM_BASE
            found.setdefault(parts[3], (offset, int(parts[2], 16), None))
    return found


def _xmap_symbols(text: str) -> _Symbols:
    """Symbols from a Metrowerks xMAP.

    Each overlay's section opens with `SDK_OVERLAY.<name>.START`, in overlay ID
    order, and the symbol lines that follow belong to it. A function-local
    static is named `<name>$<number>`, where the number changes between
    builds, so it is also listed under `<name>` when no other symbol has it.
    """
    found: _Symbols = {}
    overlay: int | None = None
    base = ARM9_LOAD_ADDRESS
    overlays = 0
    for line in text.splitlines():
        start = re.match(r"#>([0-9A-F]{8})\s+SDK_OVERLAY\.\w+\.START ", line)
        if start:
            overlay, base = overlays, int(start.group(1), 16)
            overlays += 1
            continue
        symbol = re.match(
            r"\s+([0-9A-F]{8}) ([0-9A-F]{8}) \.\w+\s+([^.\s]\S*)\t\(", line
        )
        if symbol:
            address, size = int(symbol.group(1), 16), int(symbol.group(2), 16)
            found.setdefault(symbol.group(3), (address - base, size, overlay))
    statics: dict[str, set[tuple[int, int, int | None]]] = {}
    for name, entry in found.items():
        stem, separator, _ = name.partition("$")
        if separator and stem:
            statics.setdefault(stem, set()).add(entry)
    for stem, entries in statics.items():
        if stem not in found and len(entries) == 1:
            found[stem] = entries.pop()
    return found


def _symbols(project: str, filename: str) -> _Symbols:
    text = read(project, filename, kind="symbols")
    return _xmap_symbols(text) if filename.endswith(".xMAP") else _gba_symbols(text)


def _special_indices(project: str) -> dict[str, int]:
    """`handler -> gSpecials index`, in `def_special` order."""
    handlers = re.findall(
        r"^\s*def_special\s+(\w+)", read(project, _SPECIALS_PATH), re.M
    )
    indices: dict[str, int] = {}
    for index, handler in enumerate(handlers):
        indices.setdefault(handler, index)
    return indices


def _retail_rom(table: str, profile: dict[str, Any]) -> tuple[bytes, str]:
    """The retail ROM for `table` and its SHA-256, checked against the profile."""
    try:
        data = local_path(local_config()["games"][table]["patched_rom"]).read_bytes()
    except (OSError, KeyError) as error:
        raise SystemExit(
            f"{table}: pointer sites need its retail ROM in {GAMES_CONFIG} ({error!r})"
        ) from error
    digest = hashlib.sha256(data).hexdigest()
    known = {
        entry["value"] for entry in profile["hashes"] if entry["algorithm"] == "sha256"
    }
    if digest not in known:
        raise SystemExit(f"{table}: the configured ROM is not the retail build")
    return data, digest


def _pointer_sites(rom: bytes, addresses: set[int]) -> dict[int, list[int]]:
    """Every 4-byte-aligned offset in `rom` holding one of `addresses`."""
    sites: dict[int, list[int]] = {address: [] for address in addresses}
    aligned = rom[: len(rom) // 4 * 4]
    for index, (word,) in enumerate(struct.iter_unpack("<I", aligned)):
        if word in sites:
            sites[word].append(index * 4)
    return sites


def _hex_list(values: list[int]) -> list[str]:
    if not values:
        return ["pointers = []"]
    rows = [values[start : start + 6] for start in range(0, len(values), 6)]
    return [
        "pointers = [",
        *("    " + " ".join(f"0x{value:x}," for value in row) for row in rows),
        "]",
    ]


def generate() -> dict[str, str]:
    outputs = {}
    profiles = _profiles()
    for table, (symbols, specials) in sorted(_profile_references(profiles).items()):
        project, filename = TABLES[table]
        known = _symbols(project, filename)
        missing = sorted(symbols - known.keys())
        if missing:
            raise SystemExit(f"{table}: unknown symbols {missing}")
        special_indices = _special_indices(project) if specials else {}
        repository, commit = pinned(project, "symbols")
        sources = f"{repository}@{commit[:12]} ({filename})"
        if specials:
            sources += f" and @{pinned(project)[1][:12]} ({_SPECIALS_PATH})"
        lines = [f"# Generated by scripts/generate/profile_symbols.py from {sources}."]
        sites: dict[int, list[int]] = {}
        if filename.endswith(".sym"):
            rom, digest = _retail_rom(table, profiles[table])
            sites = _pointer_sites(
                rom, {known[name][0] + GBA_ROM_BASE for name in symbols}
            )
            lines.append(f"# Pointer sites from the retail ROM with SHA-256 {digest}.")
        lines += ["# Do not edit.", ""]
        for name in sorted(symbols):
            offset, size, overlay = known[name]
            lines += [f"[symbols.{name}]", f"offset = 0x{offset:x}", f"size = {size}"]
            if overlay is not None:
                lines.append(f"overlay = {overlay}")
            if sites:
                address = offset + GBA_ROM_BASE
                lines.append(f"address = 0x{address:x}")
                lines += _hex_list(sites[address])
            lines.append("")
        if specials:
            lines.append("[specials]")
            for name in sorted(specials):
                if name not in special_indices:
                    raise SystemExit(f"{table}: unknown special {name!r}")
                lines.append(f"{name} = {special_indices[name]}")
            lines.append("")
        outputs[f"{table}.toml"] = "\n".join(lines).rstrip("\n") + "\n"
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if out of date")
    args = parser.parse_args()
    outputs = {OUTPUT / name: text for name, text in generate().items()}
    check_or_write(outputs, check=args.check)


if __name__ == "__main__":
    main()

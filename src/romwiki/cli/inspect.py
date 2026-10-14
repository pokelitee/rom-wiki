"""`romwiki inspect`: identify one ROM image."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from romwiki.cli.common import SubParsers, add_input_arguments, inspect_input
from romwiki.pipeline.build.manifest import create_manifest, write_manifest
from romwiki.pipeline.extraction.identify import InspectionResult


def add_parser(subparsers: SubParsers) -> None:
    inspect_parser = subparsers.add_parser("inspect", help="identify a ROM image")
    add_input_arguments(inspect_parser)
    inspect_parser.add_argument("--json", action="store_true", help="emit JSON")
    inspect_parser.add_argument(
        "--manifest-output",
        type=Path,
        help="write a versioned input manifest to this path",
    )
    inspect_parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> None:
    result = inspect_input(args)
    if args.manifest_output is not None:
        write_manifest(create_manifest(result), args.manifest_output)
        print(f"Wrote manifest: {args.manifest_output}")
    if args.manifest_output is None or args.json:
        _print_inspection(result, as_json=args.json)


def _print_inspection(result: InspectionResult, *, as_json: bool) -> None:
    data = result.to_dict()
    if as_json:
        print(json.dumps(data, indent=2, sort_keys=True))
        return

    profile = data["profile"]
    print(f"Title: {data['header']['title']}")
    print(f"Game code: {data['header']['game_code']}")
    print(f"ROM version: {data['header']['rom_version']}")
    print(f"Size: {data['size']} bytes")
    print(f"Files: {data['header']['filesystem_file_count']}")
    print(f"SHA-256: {data['hashes']['sha256']}")
    if profile:
        print(f"Profile: {profile['name']} ({profile['variant']})")
        print(f"Engine: {profile['engine']}")
    else:
        print("Profile: unknown")

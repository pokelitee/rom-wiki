from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

from romwiki.errors import RomWikiError
from romwiki.pipeline.identify import InspectionResult, inspect_rom
from romwiki.pipeline.manifest import create_manifest, write_manifest
from romwiki.sites import SiteCatalog, build_sites


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="romwiki",
        description="Extract structured Pokemon ROM data for static wikis.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="identify a ROM image")
    _add_input_arguments(inspect_parser)
    inspect_parser.add_argument("--json", action="store_true", help="emit JSON")

    manifest_parser = subparsers.add_parser(
        "manifest", help="write a machine-readable input manifest"
    )
    _add_input_arguments(manifest_parser)
    manifest_parser.add_argument(
        "--output",
        type=Path,
        default=Path("build/data/manifest.json"),
        help="manifest output path",
    )

    site_parser = subparsers.add_parser(
        "site", help="list or build independently configured wiki sites"
    )
    site_subparsers = site_parser.add_subparsers(dest="site_command", required=True)
    list_parser = site_subparsers.add_parser("list", help="list configured sites")
    _add_site_root_argument(list_parser)

    build_site_parser = site_subparsers.add_parser(
        "build", help="build selected MkDocs sites into one Pages artifact"
    )
    build_site_parser.add_argument("site_ids", nargs="*", help="site identifiers")
    build_site_parser.add_argument(
        "--all", action="store_true", dest="build_all", help="build published sites"
    )
    build_site_parser.add_argument(
        "--output", type=Path, default=Path("dist"), help="artifact output directory"
    )
    _add_site_root_argument(build_site_parser)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command in {"inspect", "manifest"}:
            result = inspect_rom(args.rom, args.profiles_dir)
        if args.command == "inspect":
            _print_inspection(result, as_json=args.json)
        elif args.command == "manifest":
            write_manifest(create_manifest(result), args.output)
            print(f"Wrote manifest: {args.output}")
        elif args.command == "site":
            catalog = SiteCatalog.load(args.root)
            if args.site_command == "list":
                _print_sites(catalog)
            elif args.site_command == "build":
                built = build_sites(
                    catalog,
                    args.output,
                    site_ids=args.site_ids,
                    build_all=args.build_all,
                )
                for site in built:
                    print(f"Built {site.id}: {site.output_path(args.output.resolve())}")
        return 0
    except RomWikiError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


def _add_input_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("rom", type=Path, help="path to a locally supplied ROM image")
    parser.add_argument(
        "--profiles-dir",
        type=Path,
        default=Path("profiles"),
        help="directory containing game and hack profiles",
    )


def _add_site_root_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="repository root containing portal and games",
    )


def _print_sites(catalog: SiteCatalog) -> None:
    for site in catalog.sites:
        state = "published" if site.published else "draft"
        location = "/" if not site.slug else f"/{site.slug}/"
        print(f"{site.id:<24} {state:<9} {location}  {site.name}")


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

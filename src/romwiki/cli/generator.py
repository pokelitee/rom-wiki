"""Commands that prepare the browser generator's downloads."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from romwiki.cli.common import (
    LOG,
    SubParsers,
    add_site_root_argument,
    resolve_pokedb_root,
)
from romwiki.sites.generator_runtime import (
    create_pokedb_archive,
    restore_pokedb_archive,
    write_generator_bundle,
)
from romwiki.sites.snapshot_release import POKEDB_PACKS, publish_snapshot


def add_parser(subparsers: SubParsers) -> None:
    pack = subparsers.add_parser(
        "pack-pokedb",
        help="package, pin and upload the PokéDB packs the browser generator loads",
    )
    pack.add_argument(
        "--pokedb-root",
        type=Path,
        help="PokéDB root containing gen<N> directories (default: from games config)",
    )
    pack.add_argument("--games-config", type=Path, default=Path(".local/games.toml"))
    pack.add_argument("--output", type=Path, default=Path(".romwiki/generator-runtime"))
    pack.add_argument(
        "--pin",
        type=Path,
        default=Path(POKEDB_PACKS.pinned_manifest),
        help="committed manifest to pin the new archive in",
    )
    pack.add_argument(
        "--no-upload",
        dest="upload",
        action="store_false",
        help="pin the archive without uploading it to the snapshots release",
    )
    pack.set_defaults(handler=run_pack_pokedb)
    unpack = subparsers.add_parser(
        "restore-pokedb", help="verify and unpack the pinned PokéDB packs"
    )
    unpack.add_argument("directory", type=Path, help="pin directory with the archive")
    unpack.add_argument("--output", type=Path, required=True)
    unpack.set_defaults(handler=run_restore_pokedb)
    bundle = subparsers.add_parser(
        "bundle-generator", help="lay out the browser generator's downloads"
    )
    add_site_root_argument(bundle)
    bundle.add_argument("--wheel", type=Path, required=True, help="romwiki wheel")
    bundle.add_argument(
        "--packs", type=Path, required=True, help="directory of restored PokéDB packs"
    )
    bundle.add_argument("--output", type=Path, default=Path("web/public/generator"))
    bundle.set_defaults(handler=run_bundle_generator)


def run_pack_pokedb(args: argparse.Namespace) -> None:
    pokedb_root = resolve_pokedb_root(args.pokedb_root, args.games_config)
    path = create_pokedb_archive(pokedb_root, args.output)
    LOG.info("Prepared PokéDB packs: %s", path)
    args.pin.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path.parent / "manifest.json", args.pin)
    LOG.info("Pinned the packs in %s", args.pin)
    if not args.upload:
        return
    removed = publish_snapshot(path, POKEDB_PACKS)
    LOG.info("Published %s to the snapshots release", path.name)
    if removed:
        LOG.info("Deleted superseded PokéDB packs: %s", ", ".join(removed))


def run_restore_pokedb(args: argparse.Namespace) -> None:
    count = restore_pokedb_archive(args.directory, args.output)
    LOG.info("Restored %s PokéDB packs to %s", count, args.output)


def run_bundle_generator(args: argparse.Namespace) -> None:
    write_generator_bundle(args.root, args.wheel, args.packs, args.output)
    LOG.info("Wrote the browser generator bundle to %s", args.output)

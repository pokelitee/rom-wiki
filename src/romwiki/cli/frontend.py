"""ROM-free frontend export commands."""

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
from romwiki.sites.frontend import export_frontend
from romwiki.sites.frontend_snapshot import (
    create_frontend_snapshot,
    restore_frontend_snapshot,
)
from romwiki.sites.generator_runtime import (
    create_pokedb_archive,
    restore_pokedb_archive,
    write_generator_bundle,
)
from romwiki.sites.snapshot_release import POKEDB_PACKS, publish_snapshot


def add_parser(subparsers: SubParsers) -> None:
    parser = subparsers.add_parser(
        "export-web", help="export versioned React frontend data"
    )
    add_site_root_argument(parser)
    parser.add_argument("--output", type=Path, default=Path("web/public/data"))
    parser.add_argument(
        "--data-root",
        type=Path,
        help="local generated data root containing comparison outputs",
    )
    parser.set_defaults(handler=run_export)
    snapshot = subparsers.add_parser(
        "snapshot-web",
        help="package, pin and upload a complete ROM-free frontend snapshot",
    )
    snapshot.add_argument("--source", type=Path, default=Path("web/public/data"))
    snapshot.add_argument(
        "--output", type=Path, default=Path(".romwiki/frontend-snapshot")
    )
    snapshot.add_argument(
        "--pin",
        type=Path,
        default=Path("sites/frontend-snapshot/manifest.json"),
        help="committed manifest to pin the new snapshot in",
    )
    snapshot.add_argument(
        "--no-pin",
        dest="pin",
        action="store_const",
        const=None,
        help="prepare a trial snapshot without pinning or uploading it",
    )
    snapshot.add_argument(
        "--no-upload",
        dest="upload",
        action="store_false",
        help="pin the snapshot without uploading it to the snapshots release",
    )
    snapshot.set_defaults(handler=run_snapshot)
    restore = subparsers.add_parser(
        "restore-web", help="restore a checksum-pinned frontend snapshot"
    )
    restore.add_argument("snapshot", type=Path)
    restore.add_argument("--output", type=Path, default=Path("web/public/data"))
    restore.set_defaults(handler=run_restore)
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


def run_export(args: argparse.Namespace) -> None:
    count = export_frontend(args.root, args.output, data_root=args.data_root)
    LOG.info("Exported %s game wikis to %s", count, args.output)


def run_snapshot(args: argparse.Namespace) -> None:
    path = create_frontend_snapshot(args.source, args.output)
    LOG.info("Prepared frontend snapshot: %s", path)
    if args.pin is None:
        return
    shutil.copyfile(path.parent / "manifest.json", args.pin)
    LOG.info("Pinned the snapshot in %s", args.pin)
    if not args.upload:
        return
    removed = publish_snapshot(path)
    LOG.info("Published %s to the snapshots release", path.name)
    if removed:
        LOG.info("Deleted superseded snapshots: %s", ", ".join(removed))


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


def run_restore(args: argparse.Namespace) -> None:
    count = restore_frontend_snapshot(args.snapshot, args.output)
    LOG.info("Restored %s frontend resources", count)

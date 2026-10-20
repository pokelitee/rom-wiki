"""ROM-free frontend export commands."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from romwiki.cli.common import LOG, SubParsers, add_site_root_argument
from romwiki.sites.frontend import export_frontend
from romwiki.sites.frontend_snapshot import (
    create_frontend_snapshot,
    restore_frontend_snapshot,
)
from romwiki.sites.snapshot_release import publish_snapshot


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


def run_restore(args: argparse.Namespace) -> None:
    count = restore_frontend_snapshot(args.snapshot, args.output)
    LOG.info("Restored %s frontend resources", count)

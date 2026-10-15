"""ROM-free frontend export commands."""

from __future__ import annotations

import argparse
from pathlib import Path

from romwiki.cli.common import LOG, SubParsers, add_site_root_argument
from romwiki.sites.frontend import export_frontend
from romwiki.sites.frontend_snapshot import (
    create_frontend_snapshot,
    restore_frontend_snapshot,
)


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
        "snapshot-web", help="prepare a complete ROM-free frontend snapshot locally"
    )
    snapshot.add_argument("--source", type=Path, default=Path("web/public/data"))
    snapshot.add_argument(
        "--output", type=Path, default=Path(".romwiki/frontend-snapshot")
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


def run_restore(args: argparse.Namespace) -> None:
    count = restore_frontend_snapshot(args.snapshot, args.output)
    LOG.info("Restored %s frontend resources", count)

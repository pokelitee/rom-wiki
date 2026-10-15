"""`romwiki site`: list sites and manage generated-data snapshots."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from romwiki.cli.common import LOG, SubParsers, add_site_root_argument
from romwiki.cli.frontend import add_parser as add_frontend_parser
from romwiki.sites import (
    SiteCatalog,
    create_generated_wiki_snapshot,
    publish_generated_wiki_snapshot,
    restore_generated_wiki_snapshot,
)
from romwiki.sites.snapshot import DEFAULT_SNAPSHOT_URL, SNAPSHOT_RELEASE_REPOSITORY
from romwiki.util.logging import timed_operation


def add_parser(subparsers: SubParsers) -> None:
    site_parser = subparsers.add_parser(
        "site", help="list sites and snapshot, restore, or publish generated data"
    )
    site_subparsers = site_parser.add_subparsers(dest="site_command", required=True)
    add_frontend_parser(site_subparsers)
    list_parser = site_subparsers.add_parser("list", help="list configured sites")
    list_parser.add_argument(
        "--json",
        action="store_true",
        help="emit compact machine-readable site metadata",
    )
    list_parser.add_argument(
        "--published",
        action="store_true",
        help="list published sites only",
    )
    add_site_root_argument(list_parser)
    list_parser.set_defaults(handler=run_list)

    snapshot_parser = site_subparsers.add_parser(
        "snapshot", help="archive generated, ROM-free public data"
    )
    snapshot_parser.add_argument(
        "--output",
        type=Path,
        default=Path("sites/generated-wiki"),
    )
    snapshot_parser.add_argument(
        "--pokedb-root",
        type=Path,
        help="directory containing the gen<N> PokéDB outputs used for generation; "
        "recorded as provenance in the snapshot manifest",
    )
    add_site_root_argument(snapshot_parser)
    snapshot_parser.set_defaults(handler=run_snapshot)
    restore_parser = site_subparsers.add_parser(
        "restore-snapshot", help="restore generated public data"
    )
    restore_parser.add_argument(
        "archive",
        type=Path,
        nargs="?",
        default=Path("sites/generated-wiki"),
    )
    restore_parser.add_argument(
        "--site", action="append", default=[], help="restore only this site"
    )
    restore_parser.add_argument(
        "--snapshot-url",
        help="base URL of published snapshot archives (default: "
        "$ROMWIKI_SNAPSHOT_URL, or the pokelitee/rom-wiki snapshots release)",
    )
    add_site_root_argument(restore_parser)
    restore_parser.set_defaults(handler=run_restore_snapshot)
    publish_parser = site_subparsers.add_parser(
        "publish-snapshot",
        help="upload snapshot archives to the GitHub snapshots release",
    )
    publish_parser.add_argument(
        "directory",
        type=Path,
        nargs="?",
        default=Path("sites/generated-wiki"),
    )
    publish_parser.add_argument(
        "--repo",
        default=SNAPSHOT_RELEASE_REPOSITORY,
        help=f"GitHub repository that hosts the release "
        f"(default: {SNAPSHOT_RELEASE_REPOSITORY})",
    )
    publish_parser.set_defaults(handler=run_publish_snapshot)


def run_list(args: argparse.Namespace) -> None:
    catalog = SiteCatalog.load(args.root)
    sites = catalog.published() if args.published else catalog.sites
    if args.json:
        print(
            json.dumps(
                [
                    {
                        "id": site.id,
                        "data_driven": bool(site.game and site.game.data_driven),
                    }
                    for site in sites
                ],
                separators=(",", ":"),
            )
        )
        return
    for site in sites:
        state = "published" if site.published else "draft"
        location = "/" if not site.slug else f"/{site.slug}/"
        print(f"{site.id:<24} {state:<9} {location}  {site.name}")


def run_snapshot(args: argparse.Namespace) -> None:
    with timed_operation(LOG, "Generated wiki snapshot"):
        count = create_generated_wiki_snapshot(
            args.root, args.output, pokedb_root=args.pokedb_root
        )
    LOG.info(
        "Archived %s generated wiki files: %s",
        f"{count:,}",
        args.output,
    )


def run_restore_snapshot(args: argparse.Namespace) -> None:
    with timed_operation(LOG, "Generated wiki snapshot restore"):
        count = restore_generated_wiki_snapshot(
            args.root,
            args.archive,
            site_ids=tuple(args.site),
            download_url=(
                args.snapshot_url
                or os.environ.get("ROMWIKI_SNAPSHOT_URL")
                or DEFAULT_SNAPSHOT_URL
            ),
        )
    LOG.info(
        "Restored %s generated wiki files: %s",
        f"{count:,}",
        args.archive,
    )


def run_publish_snapshot(args: argparse.Namespace) -> None:
    uploaded = publish_generated_wiki_snapshot(args.directory, repository=args.repo)
    LOG.info("Uploaded %s snapshot archives to %s", f"{len(uploaded):,}", args.repo)

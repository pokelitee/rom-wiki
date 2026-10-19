"""`romwiki site`: list sites and manage the frontend publication."""

from __future__ import annotations

import argparse
import json

from romwiki.cli.common import SubParsers, add_site_root_argument
from romwiki.cli.frontend import add_parser as add_frontend_parser
from romwiki.sites import SiteCatalog


def add_parser(subparsers: SubParsers) -> None:
    site_parser = subparsers.add_parser(
        "site",
        help="list sites and export, snapshot, or restore the frontend publication",
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


def run_list(args: argparse.Namespace) -> None:
    catalog = SiteCatalog.load(args.root)
    sites = catalog.published() if args.published else catalog.sites
    if args.json:
        print(
            json.dumps(
                [{"id": site.id, "kind": site.kind} for site in sites],
                separators=(",", ":"),
            )
        )
        return
    for site in sites:
        state = "published" if site.published else "draft"
        location = "/" if not site.slug else f"/{site.slug}/"
        print(f"{site.id:<24} {state:<9} {location}  {site.name}")

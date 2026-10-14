"""`romwiki site`: list, build, serve, audit, snapshot, and restore sites."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from romwiki.cli.common import (
    LOG,
    SubParsers,
    add_dev_argument,
    add_jobs_argument,
    add_site_root_argument,
    report_site_audit,
    site_output,
)
from romwiki.sites import (
    SiteCatalog,
    audit_site,
    build_sites,
    create_generated_wiki_snapshot,
    publish_generated_wiki_snapshot,
    restore_generated_wiki_snapshot,
    serve_sites,
)
from romwiki.sites.build_state import current_site_build_state, site_build_fingerprint
from romwiki.sites.snapshot import DEFAULT_SNAPSHOT_URL, SNAPSHOT_RELEASE_REPOSITORY
from romwiki.util.logging import timed_operation


def add_parser(subparsers: SubParsers) -> None:
    site_parser = subparsers.add_parser(
        "site", help="list, build, serve, audit, snapshot, and restore wiki sites"
    )
    site_subparsers = site_parser.add_subparsers(dest="site_command", required=True)
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

    build_site_parser = site_subparsers.add_parser(
        "build", help="build selected MkDocs sites into one Pages artifact"
    )
    build_site_parser.add_argument("site_ids", nargs="*", help="site identifiers")
    build_site_parser.add_argument(
        "--all", action="store_true", dest="build_all", help="build published sites"
    )
    build_site_parser.add_argument(
        "--output",
        type=Path,
        help="artifact output directory (default: dist, or build/mkdocs-dev with --dev)",
    )
    build_site_parser.add_argument(
        "--incremental",
        action="store_true",
        help="reuse a compatible artifact and rebuild only changed MkDocs inputs",
    )
    build_site_parser.add_argument(
        "--reuse-unchanged",
        action="store_true",
        help="skip verified unchanged sites and clean-build changed sites",
    )
    add_dev_argument(
        build_site_parser,
        help_text="use lightweight development MkDocs configurations",
    )
    add_jobs_argument(build_site_parser)
    add_site_root_argument(build_site_parser)
    build_site_parser.set_defaults(handler=run_build)
    fingerprint_parser = site_subparsers.add_parser(
        "fingerprint", help="print a deterministic MkDocs build-input fingerprint"
    )
    fingerprint_parser.add_argument("site_id")
    fingerprint_parser.add_argument("--output", type=Path, default=Path("dist"))
    add_site_root_argument(fingerprint_parser)
    fingerprint_parser.set_defaults(handler=run_fingerprint)
    serve_site_parser = site_subparsers.add_parser(
        "serve",
        help="build, serve, and live-reload selected wiki sites",
    )
    serve_site_parser.add_argument("site_ids", nargs="*", help="site identifiers")
    serve_site_parser.add_argument(
        "--all",
        action="store_true",
        dest="serve_all",
        help="serve all published sites",
    )
    serve_site_parser.add_argument(
        "--dev",
        action="store_true",
        help="use lightweight development MkDocs configurations",
    )
    serve_site_parser.add_argument(
        "--output",
        type=Path,
        default=Path("build/mkdocs-dev"),
        help="served artifact directory",
    )
    serve_site_parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="interface to bind (default: 127.0.0.1)",
    )
    serve_site_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="port to bind (default: 8000)",
    )
    add_site_root_argument(serve_site_parser)
    serve_site_parser.set_defaults(handler=run_serve)
    audit_site_parser = site_subparsers.add_parser(
        "audit", help="validate a rendered multi-site artifact"
    )
    audit_site_parser.add_argument("artifact", type=Path)
    audit_site_parser.add_argument(
        "--max-page-kb",
        type=int,
        default=512,
        help="maximum rendered HTML page size in KiB (default: 512)",
    )
    audit_site_parser.add_argument(
        "--max-images",
        type=int,
        default=150,
        help="image count that triggers a warning on one page (default: 150)",
    )
    audit_site_parser.add_argument(
        "--base-url",
        help="deployment base URL used to resolve absolute project-site links",
    )
    audit_site_parser.add_argument(
        "--no-cache", action="store_true", help="parse every HTML page"
    )
    add_jobs_argument(audit_site_parser)
    audit_site_parser.set_defaults(handler=run_audit)
    snapshot_parser = site_subparsers.add_parser(
        "snapshot", help="archive generated, ROM-free wiki Markdown"
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
        "restore-snapshot", help="restore generated wiki Markdown"
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


def run_audit(args: argparse.Namespace) -> None:
    with timed_operation(LOG, "Site audit"):
        report = audit_site(
            args.artifact,
            max_html_bytes=args.max_page_kb * 1024,
            max_images_per_page=args.max_images,
            base_url=args.base_url,
            jobs=args.jobs,
            cache_path=(
                None if args.no_cache else Path(".romwiki/audit-cache.sqlite3")
            ),
        )
    report_site_audit(report)


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


def run_build(args: argparse.Namespace) -> None:
    catalog = SiteCatalog.load(args.root)
    output = site_output(args.output, dev=args.dev)
    with timed_operation(LOG, "Site builds"):
        built = build_sites(
            catalog,
            output,
            site_ids=args.site_ids,
            build_all=args.build_all,
            dev=args.dev,
            jobs=args.jobs,
            incremental=args.incremental,
            reuse_unchanged=args.reuse_unchanged,
            hash_contents=args.reuse_unchanged,
            site_url=os.environ.get("ROMWIKI_SITE_URL"),
        )
    for site in built:
        LOG.info(
            "Built %s: %s",
            site.id,
            site.output_path(output.resolve()),
        )


def run_serve(args: argparse.Namespace) -> None:
    catalog = SiteCatalog.load(args.root)
    serve_sites(
        catalog,
        args.output,
        site_ids=args.site_ids,
        serve_all=args.serve_all,
        dev=args.dev,
        host=args.host,
        port=args.port,
    )


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


def run_fingerprint(args: argparse.Namespace) -> None:
    catalog = SiteCatalog.load(args.root)
    site = catalog.get(args.site_id)
    state = current_site_build_state(
        catalog,
        site,
        args.output.resolve(),
        dev=False,
        site_url=os.environ.get("ROMWIKI_SITE_URL"),
        hash_contents=True,
    )
    print(site_build_fingerprint(state))

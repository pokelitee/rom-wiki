"""ROM Wiki command-line interface.

Each command group owns its parser construction and handlers in a sibling
module; leaf parsers register their handler through `set_defaults(handler=...)`.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from romwiki.cli import baseline, build, extract, inspect, regenerate, site
from romwiki.cli.common import LOG
from romwiki.util.errors import RomWikiError
from romwiki.util.logging import configure_logging

__all__ = ["build_parser", "main"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="romwiki",
        description="Extract structured Pokémon ROM data for a shared React reference app.",
    )
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="show detailed diagnostic output",
    )
    output_group.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="show warnings and errors only",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect.add_parser(subparsers)
    extract.add_parser(subparsers)
    build.add_parser(subparsers)
    regenerate.add_generate_parser(subparsers)
    baseline.add_parser(subparsers)
    site.add_parser(subparsers)
    return parser


EXIT_FAILURE = 1


def main(argv: Sequence[str] | None = None) -> int:
    # argparse exits with status 2 for usage errors before a handler runs, so
    # domain failures use a distinct status.
    args = build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    configure_logging(verbose=args.verbose, quiet=args.quiet)
    try:
        args.handler(args)
        return 0
    except RomWikiError as error:
        LOG.error("%s", error)
        return EXIT_FAILURE

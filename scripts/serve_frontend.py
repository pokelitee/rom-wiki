"""Serve a frontend build below its Pages prefix without SPA path rewrites."""

from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class PagesHandler(SimpleHTTPRequestHandler):
    def do_GET(self) -> None:
        if not self.path.startswith("/rom-wiki/"):
            self.send_error(404)
            return
        self.path = self.path.removeprefix("/rom-wiki")
        super().do_GET()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=4173)
    parser.add_argument(
        "--directory",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "web/dist",
    )
    args = parser.parse_args()
    handler = partial(PagesHandler, directory=str(args.directory))
    with ThreadingHTTPServer(("127.0.0.1", args.port), handler) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()

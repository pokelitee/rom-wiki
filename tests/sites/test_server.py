from __future__ import annotations

import tempfile
import threading
import unittest
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen

from romwiki.sites.server import (
    DevelopmentRequestHandler,
    ReloadState,
    _validate_server_options,
)
from romwiki.util.errors import SiteError


class DevelopmentServerTests(unittest.TestCase):
    def test_rejects_output_inside_watched_sources_and_invalid_ports(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            watched_output = root / "sites" / "preview"

            with self.assertRaises(SiteError):
                _validate_server_options(root, watched_output, 8000)
            with self.assertRaises(SiteError):
                _validate_server_options(root, root / "build", 70000)

    def test_html_responses_include_live_reload_and_version_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "index.html").write_text(
                "<!doctype html><body><p>ROM Wiki</p></body>",
                encoding="utf-8",
            )
            reload_state = ReloadState()
            handler = partial(
                DevelopmentRequestHandler,
                directory=str(root),
                reload_state=reload_state,
            )
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                with urlopen(f"http://{host}:{port}/", timeout=5) as response:
                    html = response.read().decode()
                    self.assertEqual(response.headers["Cache-Control"], "no-store")
                self.assertIn("/__romwiki_dev__/version", html)
                self.assertIn("<p>ROM Wiki</p>", html)

                self.assertEqual(self._version(host, port), "0")
                reload_state.advance()
                self.assertEqual(self._version(host, port), "1")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    @staticmethod
    def _version(host: str, port: int) -> str:
        with urlopen(
            f"http://{host}:{port}/__romwiki_dev__/version",
            timeout=5,
        ) as response:
            return response.read().decode()


if __name__ == "__main__":
    unittest.main()

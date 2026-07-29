from __future__ import annotations

import tempfile
import threading
import unittest
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

from romwiki.sites.catalog import SiteCatalog
from romwiki.sites.server import (
    DevelopmentRequestHandler,
    ReloadState,
    _development_site_url,
    _prepare_output,
    _validate_server_options,
    serve_sites,
)
from romwiki.util.errors import SiteError


class DevelopmentServerTests(unittest.TestCase):
    def test_development_site_url_normalizes_local_bind_hosts(self) -> None:
        self.assertEqual(
            _development_site_url("127.0.0.1", 8000),
            "http://localhost:8000/",
        )
        self.assertEqual(
            _development_site_url("::", 8000),
            "http://localhost:8000/",
        )

    def test_rejects_output_inside_watched_sources_and_invalid_ports(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            watched_output = root / "sites" / "preview"

            with self.assertRaises(SiteError):
                _validate_server_options(root, watched_output, 8000)
            with self.assertRaises(SiteError):
                _validate_server_options(root, root / "build", 70000)
            with self.assertRaises(SiteError):
                _validate_server_options(root, root.parent, 8000)
            with self.assertRaises(SiteError):
                _validate_server_options(root, root / "docs" / "preview", 8000)

    def test_invalid_selection_does_not_clean_the_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "build" / "preview"
            output.mkdir(parents=True)
            stale = output / "keep.txt"
            stale.write_text("keep", encoding="utf-8")

            with self.assertRaises(SiteError):
                serve_sites(SiteCatalog(root, ()), output)

            self.assertEqual(stale.read_text(encoding="utf-8"), "keep")

    def test_preparing_output_removes_stale_site_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "preview"
            stale = output / "old-wiki" / "index.html"
            stale.parent.mkdir(parents=True)
            stale.write_text("stale", encoding="utf-8")

            _prepare_output(output)

            self.assertTrue(output.is_dir())
            self.assertFalse(stale.exists())

    def test_html_responses_include_live_reload_and_version_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "index.html").write_text(
                "<!doctype html><body><p>ROM Wiki</p></body>",
                encoding="utf-8",
            )
            (root / "app.js").write_text("console.log('ready');", encoding="utf-8")
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

                with urlopen(f"http://{host}:{port}/app.js", timeout=5) as response:
                    self.assertEqual(response.headers["Cache-Control"], "no-store")

                self.assertEqual(self._version(host, port), "0")
                reload_state.advance()
                self.assertEqual(self._version(host, port), "1")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_single_site_landing_path_redirects_to_the_wiki(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wiki = root / "platinum"
            wiki.mkdir()
            (wiki / "index.html").write_text(
                "<!doctype html><body>Platinum</body>",
                encoding="utf-8",
            )
            handler = partial(
                DevelopmentRequestHandler,
                directory=str(root),
                reload_state=ReloadState(),
                landing_path="/platinum/",
            )
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                with urlopen(f"http://{host}:{port}/", timeout=5) as response:
                    self.assertTrue(response.geturl().endswith("/platinum/"))
                    self.assertIn("Platinum", response.read().decode())
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_missing_pages_use_the_nearest_generated_404(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            game = root / "platinum"
            game.mkdir()
            (root / "404.html").write_text(
                "<!doctype html><body>Portal not found</body>",
                encoding="utf-8",
            )
            (game / "404.html").write_text(
                "<!doctype html><body>Platinum not found</body>",
                encoding="utf-8",
            )
            handler = partial(
                DevelopmentRequestHandler,
                directory=str(root),
                reload_state=ReloadState(),
            )
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                with self.assertRaises(HTTPError) as game_error:
                    urlopen(f"http://{host}:{port}/platinum/missing/", timeout=5)
                self.assertEqual(game_error.exception.code, 404)
                self.assertIn(
                    "Platinum not found",
                    game_error.exception.read().decode(),
                )

                with self.assertRaises(HTTPError) as portal_error:
                    urlopen(f"http://{host}:{port}/missing/", timeout=5)
                self.assertEqual(portal_error.exception.code, 404)
                self.assertIn(
                    "Portal not found",
                    portal_error.exception.read().decode(),
                )
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

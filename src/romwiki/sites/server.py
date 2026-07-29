from __future__ import annotations

import logging
import threading
from collections.abc import Sequence
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from romwiki.sites.build import build_sites
from romwiki.sites.catalog import SiteCatalog
from romwiki.util.errors import SiteError

_LOG = logging.getLogger("romwiki")
_RELOAD_ENDPOINT = "/__romwiki_dev__/version"
_RELOAD_SCRIPT = f"""
<script>
(() => {{
  let version;
  const check = async () => {{
    try {{
      const response = await fetch("{_RELOAD_ENDPOINT}", {{ cache: "no-store" }});
      const next = await response.text();
      if (version === undefined) version = next;
      else if (version !== next) location.reload();
    }} catch (error) {{
      // The next interval retries while the development server is rebuilding.
    }}
  }};
  check();
  window.setInterval(check, 750);
}})();
</script>
""".strip().encode()
_WATCHED_SUFFIXES = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".md",
    ".py",
    ".toml",
    ".yaml",
    ".yml",
}


class ReloadState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._version = 0

    def current(self) -> str:
        with self._lock:
            return str(self._version)

    def advance(self) -> None:
        with self._lock:
            self._version += 1


class DevelopmentRequestHandler(SimpleHTTPRequestHandler):
    server_version = "ROMWikiDev/1.0"

    def __init__(
        self,
        *args: Any,
        directory: str,
        reload_state: ReloadState,
        **kwargs: Any,
    ) -> None:
        self._root = Path(directory).resolve()
        self._reload_state = reload_state
        super().__init__(*args, directory=directory, **kwargs)

    def do_GET(self) -> None:
        if urlsplit(self.path).path == _RELOAD_ENDPOINT:
            self._send_reload_version()
            return
        html_path = self._requested_html_path()
        if html_path is None:
            super().do_GET()
            return
        try:
            content = html_path.read_bytes()
        except OSError:
            super().do_GET()
            return
        marker = b"</body>"
        position = content.rfind(marker)
        if position >= 0:
            content = (
                content[:position] + _RELOAD_SCRIPT + marker + content[position + 7 :]
            )
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format: str, *args: Any) -> None:
        _LOG.debug("Development server: " + format, *args)

    def _send_reload_version(self) -> None:
        content = self._reload_state.current().encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def _requested_html_path(self) -> Path | None:
        request_path = unquote(urlsplit(self.path).path).lstrip("/")
        candidate = (self._root / request_path).resolve()
        if not candidate.is_relative_to(self._root):
            return None
        if candidate.is_dir():
            candidate /= "index.html"
        return (
            candidate if candidate.is_file() and candidate.suffix == ".html" else None
        )


def serve_sites(
    catalog: SiteCatalog,
    output_root: Path,
    *,
    site_ids: Sequence[str] = (),
    serve_all: bool = False,
    dev: bool = False,
    host: str = "127.0.0.1",
    port: int = 8000,
) -> None:
    resolved_output = output_root.resolve()
    _validate_server_options(catalog.root, resolved_output, port)
    build_sites(
        catalog,
        resolved_output,
        site_ids=site_ids,
        build_all=serve_all,
        dev=dev,
    )

    reload_state = ReloadState()
    changes = threading.Event()
    stop = threading.Event()
    observer = _start_source_observer(catalog.root, changes)
    rebuild = threading.Thread(
        target=_rebuild_worker,
        args=(
            catalog,
            resolved_output,
            site_ids,
            serve_all,
            dev,
            changes,
            stop,
            reload_state,
        ),
        name="romwiki-rebuild",
        daemon=True,
    )
    handler = partial(
        DevelopmentRequestHandler,
        directory=str(resolved_output),
        reload_state=reload_state,
    )
    try:
        server = ThreadingHTTPServer((host, port), handler)
    except OSError as error:
        raise SiteError(
            f"Could not bind development server to {host}:{port}: {error}"
        ) from error
    rebuild_started = False
    observer_started = False
    try:
        rebuild.start()
        rebuild_started = True
        observer.start()
        observer_started = True
        actual_host, actual_port = server.server_address[:2]
        display_host = (
            "localhost" if actual_host in {"0.0.0.0", "127.0.0.1"} else actual_host
        )
        _LOG.info("Serving combined wiki at http://%s:%s/", display_host, actual_port)
        _LOG.info("Watching site sources for changes; press Ctrl+C to stop")
        server.serve_forever()
    except KeyboardInterrupt:
        _LOG.info("Stopping development server")
    finally:
        stop.set()
        changes.set()
        server.server_close()
        if observer_started:
            observer.stop()
            observer.join(timeout=5)
        if rebuild_started:
            rebuild.join(timeout=5)


def _validate_server_options(root: Path, output_root: Path, port: int) -> None:
    if not 0 <= port <= 65535:
        raise SiteError(f"Development server port is out of range: {port}")
    for source in (root / "sites", root / "src" / "romwiki" / "sites"):
        resolved_source = source.resolve()
        if output_root == resolved_source or output_root.is_relative_to(
            resolved_source
        ):
            raise SiteError(
                f"Development output cannot be inside watched sources: {output_root}"
            )


def _start_source_observer(root: Path, changes: threading.Event) -> Any:
    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer
    except ImportError as error:
        raise SiteError(
            "The development server requires the docs dependencies; "
            "install the project with the 'docs' extra"
        ) from error

    class ChangeHandler(FileSystemEventHandler):
        def on_any_event(self, event: Any) -> None:
            if event.event_type not in {"created", "deleted", "modified", "moved"}:
                return
            path = Path(
                event.dest_path if event.event_type == "moved" else event.src_path
            )
            if event.is_directory or (
                path.suffix.lower() in _WATCHED_SUFFIXES
                and "__pycache__" not in path.parts
            ):
                changes.set()

    observer = Observer()
    for source in (root / "sites", root / "src" / "romwiki" / "sites"):
        if source.is_dir():
            observer.schedule(ChangeHandler(), str(source), recursive=True)
    return observer


def _rebuild_worker(
    catalog: SiteCatalog,
    output_root: Path,
    site_ids: Sequence[str],
    serve_all: bool,
    dev: bool,
    changes: threading.Event,
    stop: threading.Event,
    reload_state: ReloadState,
) -> None:
    while not stop.is_set():
        if not changes.wait(timeout=0.5):
            continue
        changes.clear()
        if stop.wait(timeout=0.2):
            break
        while changes.is_set():
            changes.clear()
            if stop.wait(timeout=0.2):
                return
        _LOG.info("Site source change detected; rebuilding combined wiki")
        try:
            build_sites(
                catalog,
                output_root,
                site_ids=site_ids,
                build_all=serve_all,
                dev=dev,
            )
        except SiteError as error:
            _LOG.error("Development rebuild failed: %s", error)
            continue
        reload_state.advance()
        _LOG.info("Development rebuild complete")

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from romwiki.sites.snapshot_release import POKEDB_PACKS, publish_snapshot
from romwiki.util.errors import SiteError


class FakeRelease:
    """Stands in for `gh`, holding the release's asset names."""

    def __init__(self, assets: set[str], main_archive: str) -> None:
        self.assets = set(assets)
        self.main_archive = main_archive
        self.calls: list[list[str]] = []

    def run(self, command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        self.calls.append(command)
        args = command[1:]
        stdout = ""
        if args[0] == "api":
            stdout = json.dumps({"archive": self.main_archive})
        elif args[:2] == ["release", "view"]:
            stdout = "\n".join(sorted(self.assets))
        elif args[:2] == ["release", "upload"]:
            self.assets.add(Path(args[3]).name)
        elif args[:2] == ["release", "delete-asset"]:
            self.assets.remove(args[3])
        return subprocess.CompletedProcess(command, 0, stdout, "")


def test_uploads_the_archive_and_keeps_only_it_and_mains(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release = FakeRelease(
        {
            "frontend-aaaa.tar.gz",
            "frontend-main.tar.gz",
            "frontend-bbbb.tar.gz",
            "notes.txt",
        },
        main_archive="frontend-main.tar.gz",
    )
    monkeypatch.setattr(subprocess, "run", release.run)

    removed = publish_snapshot(Path("out/frontend-new.tar.gz"))

    assert removed == ["frontend-aaaa.tar.gz", "frontend-bbbb.tar.gz"]
    assert release.assets == {
        "frontend-main.tar.gz",
        "frontend-new.tar.gz",
        "notes.txt",
    }


def test_an_already_published_archive_is_not_uploaded_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release = FakeRelease({"frontend-new.tar.gz"}, main_archive="frontend-new.tar.gz")
    monkeypatch.setattr(subprocess, "run", release.run)

    assert publish_snapshot(Path("frontend-new.tar.gz")) == []
    assert not any(call[1:3] == ["release", "upload"] for call in release.calls)


def test_gh_failures_are_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(command: list[str], **_: object) -> None:
        raise subprocess.CalledProcessError(1, command, stderr="HTTP 404\n")

    monkeypatch.setattr(subprocess, "run", fail)
    with pytest.raises(SiteError, match="HTTP 404"):
        publish_snapshot(Path("frontend-new.tar.gz"))


def test_a_missing_gh_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(command: list[str], **_: object) -> None:
        raise FileNotFoundError(command[0])

    monkeypatch.setattr(subprocess, "run", missing)
    with pytest.raises(SiteError, match="GitHub CLI"):
        publish_snapshot(Path("frontend-new.tar.gz"))


def test_pokedb_packs_are_published_apart_from_frontend_snapshots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release = FakeRelease(
        {"frontend-main.tar.gz", "pokedb-main.tar", "pokedb-old.tar"},
        main_archive="pokedb-main.tar",
    )
    monkeypatch.setattr(subprocess, "run", release.run)

    removed = publish_snapshot(Path("pokedb-new.tar"), POKEDB_PACKS)

    assert removed == ["pokedb-old.tar"]
    assert release.assets == {
        "frontend-main.tar.gz",
        "pokedb-main.tar",
        "pokedb-new.tar",
    }


def test_the_first_archive_of_a_kind_needs_no_pin_on_main(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release = FakeRelease({"pokedb-stray.tar"}, main_archive="unused")

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if command[1] == "api":
            raise subprocess.CalledProcessError(
                1, command, stderr="Not Found (HTTP 404)"
            )
        return release.run(command, **kwargs)

    monkeypatch.setattr(subprocess, "run", run)

    assert publish_snapshot(Path("pokedb-new.tar"), POKEDB_PACKS) == [
        "pokedb-stray.tar"
    ]
    assert release.assets == {"pokedb-new.tar"}

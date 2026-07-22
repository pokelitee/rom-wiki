from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import re
import tomllib

from romwiki.util.errors import SiteError


_PATH_PART = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


@dataclass(frozen=True, slots=True)
class DevPages:
    sections: dict[str, frozenset[str]]

    @classmethod
    def load(cls, path: Path) -> DevPages:
        try:
            with path.open("rb") as stream:
                data = tomllib.load(stream)
        except FileNotFoundError as error:
            raise SiteError(
                f"Development page manifest does not exist: {path}"
            ) from error
        except tomllib.TOMLDecodeError as error:
            raise SiteError(
                f"Invalid development page manifest {path}: {error}"
            ) from error

        pages = data.get("pages")
        if not isinstance(pages, dict):
            raise SiteError(f"Development page manifest must contain [pages]: {path}")

        sections: dict[str, frozenset[str]] = {}
        for section, values in pages.items():
            if not isinstance(section, str) or _PATH_PART.fullmatch(section) is None:
                raise SiteError(f"Invalid development page section in {path}: {section}")
            if not isinstance(values, list) or any(
                not isinstance(value, str) or _PATH_PART.fullmatch(value) is None
                for value in values
            ):
                raise SiteError(
                    f"Development pages for {section!r} must be page slugs: {path}"
                )
            if len(values) != len(set(values)):
                raise SiteError(
                    f"Duplicate development page in section {section!r}: {path}"
                )
            sections[section] = frozenset(values)
        return cls(sections)

    def pages_for(self, section: str) -> frozenset[str]:
        return self.sections.get(section, frozenset())

    def includes_document(self, source_uri: str) -> bool:
        path = PurePosixPath(source_uri)
        if path.suffix != ".md" or len(path.parts) != 2:
            return True
        section, filename = path.parts
        if section not in self.sections or filename == "index.md":
            return True
        return path.stem in self.sections[section]

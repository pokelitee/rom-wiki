"""Record and name-table sizes for one ROM build.

Hacks commonly add species, moves, and items, so a table's size is a fact of
the build being read, never the retail game's size. Where the ROM records a
table's length (an archive's members), extraction reads it; otherwise the
profile states it, and the engine's retail size is only the default for a
profile that does not. No extractor shortens a table to a retail size.
"""

from __future__ import annotations

from typing import Any

from romwiki.engines.registry import get_engine
from romwiki.util.errors import ProfileError


def profile_count(profile: Any, parameter: str, default: int) -> int:
    """Return the table size a profile declares, or the engine's retail size."""
    count = profile.int_parameter(parameter, default)
    if count < 0:
        raise ProfileError(
            f"Profile {profile.id!r} parameter {parameter!r} is negative"
        )
    return count


def leading_record_count(archive: Any, record_size: int) -> int:
    """Count the archive members before the first one larger than a record.

    Some personal archives append a non-record table after the last species
    or form (Generation V's `a/0/1/6` does), and that table is far larger
    than a record. Records themselves may be shorter than `record_size`.
    """
    count = 0
    for member in archive.members:
        if len(archive.read(member.index)) > record_size:
            break
        count += 1
    return count


def personal_archive_count(profile: Any, platform: Any, filesystem: Any) -> int:
    """Return how many species and form records the personal archive holds."""
    try:
        archive_path = profile.layout["personal"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} does not define a personal archive"
        ) from error
    archive = platform.archive_cls.from_bytes(filesystem.read(archive_path))
    return leading_record_count(
        archive, get_engine(profile.engine).personal.PERSONAL_RECORD_SIZE
    )

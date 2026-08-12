from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from romwiki.profiles.models import GameProfile
from romwiki.util.errors import ProfileError


def resolve_location_section(
    profile: GameProfile,
    *,
    header_id: int,
    internal_name: str | None,
) -> tuple[str | None, dict[str, str] | None]:
    """Resolve an explicit label or fall back to the ROM's internal map name."""

    configured = profile.location_sections
    if header_id in configured.by_header:
        return configured.by_header[header_id], {
            "source": "profile",
            "profile": profile.id,
            "key": f"header-{header_id:03}",
        }
    if internal_name is not None and internal_name in configured.by_internal_name:
        return configured.by_internal_name[internal_name], {
            "source": "profile",
            "profile": profile.id,
            "key": internal_name,
        }
    if internal_name:
        return internal_name, {
            "source": "rom",
            "field": "internal_name",
        }
    return None, None


def location_reference_label(location: Mapping[str, Any]) -> str:
    """Return an exact but readable label for a location reference."""

    name = str(location["name"])
    section_name = location.get("section_name")
    if not isinstance(section_name, str) or not section_name:
        return name
    source = location.get("section_name_source")
    if isinstance(source, Mapping) and source.get("source") == "rom":
        return f"{name} — {section_name}"
    return section_name


def validate_location_sections(
    profile: GameProfile,
    headers: Iterable[tuple[int, str | None]],
) -> None:
    """Reject selectors that do not identify an extracted header exactly."""

    header_values = tuple(headers)
    header_ids = {header_id for header_id, _ in header_values}
    internal_names = {
        internal_name for _, internal_name in header_values if internal_name is not None
    }
    missing_headers = sorted(set(profile.location_sections.by_header) - header_ids)
    missing_names = sorted(
        set(profile.location_sections.by_internal_name) - internal_names
    )
    if missing_headers or missing_names:
        details = [
            *(f"header-{header_id:03}" for header_id in missing_headers),
            *(f"internal name {name!r}" for name in missing_names),
        ]
        raise ProfileError(
            f"Profile {profile.id!r} has unmatched location section selectors: "
            + ", ".join(details)
        )

    conflicts = []
    for header_id, internal_name in header_values:
        by_header = profile.location_sections.by_header.get(header_id)
        by_internal_name = (
            profile.location_sections.by_internal_name.get(internal_name)
            if internal_name is not None
            else None
        )
        if (
            by_header is not None
            and by_internal_name is not None
            and by_header != by_internal_name
        ):
            conflicts.append(f"header-{header_id:03} / {internal_name!r}")
    if conflicts:
        raise ProfileError(
            f"Profile {profile.id!r} has conflicting location section selectors: "
            + ", ".join(conflicts)
        )

from __future__ import annotations

from typing import Any

from romwiki.engines.concerns import TrainerConcern
from romwiki.engines.registry import REMATCH_TABLE, TAG_BATTLES, get_engine
from romwiki.pipeline.extraction.identify import InspectionResult


def scripts_archive_options(profile: Any) -> dict[str, bool]:
    """Build archive-tolerance kwargs for a profile's own scripts archive.

    Hacks repack these archives loosely, and each engine family names the
    tolerance differently, so both spellings are honoured.
    """
    options = {"allow_truncated": True}
    for parameter, option in (
        (
            "field_archives_allow_incorrect_data_block_size",
            "allow_incorrect_data_block_size",
        ),
        ("field_archives_allow_trailing_data", "allow_trailing_data"),
        ("events_allow_incorrect_data_block_size", "allow_incorrect_data_block_size"),
        ("scripts_allow_incorrect_data_block_size", "allow_incorrect_data_block_size"),
        ("scripts_allow_trailing_data", "allow_trailing_data"),
    ):
        if profile.parameters.get(parameter, False):
            options[option] = True
    return options


def read_starter_branch_families(
    profile: Any,
    platform: Any,
    engine: TrainerConcern,
    filesystem: Any,
    *,
    trainer_count: int,
    starter_species: tuple[int, ...] | None,
) -> tuple[Any, ...] | None:
    """Decode starter-selected battle groups from the profile's own scripts.

    Returns `None` when the profile declares no scripts archive or starter
    table, so profiles that resolve their relationships from records alone are
    unaffected.
    """
    scripts_path = profile.layout.get("scripts")
    if scripts_path is None or starter_species is None:
        # Without the profile's starter table there is nothing to resolve an
        # index or species against, so the scripts are not even read.
        return None

    scripts = platform.archive_cls.from_bytes(
        filesystem.read(scripts_path), **scripts_archive_options(profile)
    )
    families = []
    for member in scripts.members:
        families.extend(
            engine.parse_starter_branch_families(
                scripts.read(member.index),
                script_file_id=member.index,
                trainer_count=trainer_count,
                starter_species=starter_species,
            )
        )
    return tuple(families)


def read_staged_partner_battle_families(
    profile: Any,
    platform: Any,
    engine: TrainerConcern,
    filesystem: Any,
    *,
    trainer_count: int,
    starter_species: tuple[int, ...] | None,
) -> tuple[Any, ...]:
    """Decode starter-staged tag-battle partners from the profile's own scripts.

    Returns `()` unless the engine declares tag battles, so engines that don't
    have this mechanism are unaffected. Shares `Gen4StarterBranchFamily`'s shape with
    `read_starter_branch_families`, so its results merge into the same
    `starter_branch_families` selector data with no separate rendering path.
    """
    scripts_path = profile.layout.get("scripts")
    if (
        TAG_BATTLES not in get_engine(profile.engine).capabilities
        or scripts_path is None
        or starter_species is None
    ):
        return ()

    scripts = platform.archive_cls.from_bytes(
        filesystem.read(scripts_path), **scripts_archive_options(profile)
    )
    families = []
    for member in scripts.members:
        families.extend(
            engine.parse_staged_partner_battle_families(
                scripts.read(member.index),
                script_file_id=member.index,
                trainer_count=trainer_count,
                starter_species=starter_species,
            )
        )
    return tuple(families)


def read_starter_species(
    profile: Any, platform: Any, engine: TrainerConcern, result: InspectionResult
) -> tuple[int, ...] | None:
    """Decode the species this profile's starter accessor can return.

    Without it the branch decoder cannot tell a starter comparison from an
    unrelated one sharing the same scratch variable, so it falls back to the
    stricter direct-target rule.
    """
    overlay_id = profile.parameters.get("starter_species_overlay_id")
    offset = profile.parameters.get("starter_species_offset")
    count = profile.parameters.get("starter_species_count")
    if overlay_id is None or offset is None or count is None:
        return None

    size = count * engine.STARTER_SPECIES_ENTRY_SIZE
    # Generation V overlays are BLZ-compressed; Generation IV's are stored raw,
    # so the decompressing reader is correct for both.
    read = platform.read_overlay_decompressed or platform.read_overlay
    _, overlay = read(result.image, overlay_id)
    return engine.parse_starter_species(
        overlay[offset : offset + size],
        count=count,
        species_count=engine.BASE_SPECIES_COUNT + 1,
    )


def read_rematch_table(
    profile: Any,
    platform: Any,
    engine: TrainerConcern,
    result: InspectionResult,
    *,
    trainer_count: int,
) -> tuple[dict[str, Any] | None, tuple[Any, ...] | None]:
    """Decode the profile's rematch selector table, if it declares one.

    Resolvers only see normalized records, so the selector has to be read here
    where the ROM image is still available. Profiles that declare no table get
    `None` and the resolver reports the mechanic as unresolved.
    """
    overlay_id = profile.parameters.get("trainer_rematch_overlay_id")
    offset = profile.parameters.get("trainer_rematch_offset")
    count = profile.parameters.get("trainer_rematch_count")
    if (
        REMATCH_TABLE not in get_engine(profile.engine).capabilities
        or overlay_id is None
        or offset is None
        or count is None
    ):
        return None, None

    record_size = engine.REMATCH_RECORD_SIZE
    _, overlay = platform.read_overlay(result.image, overlay_id)
    chains = engine.parse_rematch_table(
        overlay[offset : offset + count * record_size],
        count=count,
        trainer_count=trainer_count,
    )
    return (
        {"overlay_id": overlay_id, "offset": offset, "count": count},
        chains,
    )

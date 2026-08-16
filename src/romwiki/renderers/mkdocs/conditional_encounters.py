from __future__ import annotations

from typing import Any

from romwiki.pipeline.semantics.encounter_identity import (
    DAILY_SWARM_ANCHOR,
    HEADBUTT_ANCHOR,
    EncounterSourceType,
    hidden_grotto_anchor,
)
from romwiki.renderers.mkdocs.components import (
    MarkdownColumn,
    content_tabs,
    display_name,
    level_range,
    markdown_table_from_cells,
    reference_type_cell,
    rom_record_source,
    sprite_with_link,
    table_sprite_cell,
    version_variant_records,
)
from romwiki.renderers.mkdocs.references import (
    ROUTES,
    ReferenceIndex,
    entity_reference,
)
from romwiki.util.text import name_slug

_SLOT_COLUMNS = (
    MarkdownColumn("Pokémon"),
    MarkdownColumn("Type"),
    MarkdownColumn("Levels", "right"),
    MarkdownColumn("Chance", "right"),
)


def append_headbutt_encounters(
    lines: list[str],
    record: dict[str, Any],
    source_file: str,
    references: ReferenceIndex | None,
    *,
    heading_level: int = 3,
) -> None:
    lines.extend(
        [
            f"{'#' * heading_level} Headbutt encounters {{ #{HEADBUTT_ANCHOR} }}",
            "",
        ]
    )
    tabs = []
    for version, value in version_variant_records(record):
        content: list[str] = []
        for kind in ("common", "rare", "secret"):
            content.extend(
                [f"{'#' * (heading_level + 1)} {display_name(kind)} trees", ""]
            )
            if not value["pools"][kind]:
                content.extend(["—", ""])
                continue
            content.extend(
                markdown_table_from_cells(
                    _SLOT_COLUMNS,
                    (
                        (
                            _pokemon_cell(slot["pokemon"], source_file),
                            _type_cell(slot["pokemon"], references),
                            level_range(slot["minimum_level"], slot["maximum_level"]),
                            f"{slot['chance']}%",
                        )
                        for slot in value["pools"][kind]
                    ),
                )
            )
        content.extend([f"{'#' * (heading_level + 1)} Tree groups", ""])
        content.extend(
            markdown_table_from_cells(
                (
                    MarkdownColumn("Group", "right"),
                    MarkdownColumn("Kind"),
                    MarkdownColumn("Coordinates"),
                ),
                (
                    (
                        str(group["group"]),
                        display_name(group["kind"]),
                        ", ".join(f"({x}, {z})" for x, z in group["coordinates"]),
                    )
                    for group in value["tree_groups"]
                ),
            )
        )
        tabs.append((display_name(version) if version else "Encounter data", content))
    lines.extend(tabs[0][1] if len(tabs) == 1 else content_tabs(tabs))


def append_daily_swarm(
    lines: list[str],
    record: dict[str, Any],
    source_file: str,
    references: ReferenceIndex | None,
    *,
    heading_level: int = 3,
) -> None:
    lines.extend(
        [
            f"{'#' * heading_level} Daily Swarm {{ #{DAILY_SWARM_ANCHOR} }}",
            "",
            "This encounter is available only when this route is selected as the daily swarm.",
            "",
        ]
    )
    tabs = []
    for version, value in version_variant_records(record):
        tabs.append(
            (
                display_name(version) if version else "Encounter data",
                markdown_table_from_cells(
                    (
                        MarkdownColumn("Pokémon"),
                        MarkdownColumn("Type"),
                        MarkdownColumn("Levels", "right"),
                    ),
                    (
                        (
                            _pokemon_cell(value["pokemon"], source_file),
                            _type_cell(value["pokemon"], references),
                            level_range(value["minimum_level"], value["maximum_level"]),
                        ),
                    ),
                ),
            )
        )
    lines.extend(tabs[0][1] if len(tabs) == 1 else content_tabs(tabs))


def append_hidden_grotto(
    lines: list[str],
    record: dict[str, Any],
    source_file: str,
    references: ReferenceIndex | None,
    *,
    heading_level: int = 3,
    heading: str = "Hidden Grotto",
) -> None:
    grotto_id = record["grotto_id"]
    lines.extend(
        [
            f"{'#' * heading_level} {heading} {{ #{hidden_grotto_anchor(grotto_id)} }}",
            "",
            "The ROM chooses one of four groups independently from the listed pool. "
            "Pool chance and group chance are kept separate.",
            "",
        ]
    )
    tabs = []
    for version, value in version_variant_records(record):
        content = [f"{'#' * (heading_level + 1)} Pokémon", ""]
        content.extend(
            markdown_table_from_cells(
                (
                    MarkdownColumn("Pokémon"),
                    MarkdownColumn("Type"),
                    MarkdownColumn("Levels", "right"),
                    MarkdownColumn("Female", "right"),
                    MarkdownColumn("Pool", "right"),
                    MarkdownColumn("Group"),
                ),
                (
                    (
                        _pokemon_cell(slot["pokemon"], source_file),
                        _type_cell(slot["pokemon"], references),
                        level_range(slot["minimum_level"], slot["maximum_level"]),
                        f"{slot['female_percentage']}%",
                        f"{slot['pool_chance']}%",
                        chr(ord("A") + slot["group"]),
                    )
                    for slot in value["pokemon"]
                ),
            )
        )
        for key, heading in (
            ("visible_items", "Visible items"),
            ("hidden_items", "Hidden items"),
        ):
            content.extend([f"{'#' * (heading_level + 1)} {heading}", ""])
            content.extend(
                markdown_table_from_cells(
                    (
                        MarkdownColumn("Item"),
                        MarkdownColumn("Pool", "right"),
                        MarkdownColumn("Group"),
                    ),
                    (
                        (
                            ROUTES.markdown_link(
                                entity_reference(
                                    "item",
                                    slot["item"]["id"],
                                    slot["item"]["name"],
                                    slot["item"]["slug"],
                                ),
                                source_file,
                            ),
                            f"{slot['pool_chance']}%",
                            chr(ord("A") + slot["group"]),
                        )
                        for slot in value[key]
                    ),
                )
            )
        tabs.append((display_name(version) if version else "Encounter data", content))
    lines.extend(tabs[0][1] if len(tabs) == 1 else content_tabs(tabs))


def append_safari_area(
    lines: list[str],
    record: dict[str, Any],
    source_file: str,
    *,
    heading_level: int = 2,
) -> None:
    anchor = name_slug(record["area_name"])
    lines.extend(
        [
            f"{'#' * heading_level} {record['area_name']} {{ #{anchor} }}",
            "",
        ]
    )
    tabs = []
    for version, value in version_variant_records(record):
        content: list[str] = []
        for method_name, method in value["methods"].items():
            content.extend(
                [f"{'#' * (heading_level + 1)} {display_name(method_name)}", ""]
            )
            content.extend([f"{'#' * (heading_level + 2)} Base encounters", ""])
            times = ("morning", "day", "night")
            slot_count = len(method["base_pools"][times[0]])
            content.extend(
                markdown_table_from_cells(
                    (
                        MarkdownColumn("Slot", "right"),
                        *(MarkdownColumn(display_name(time)) for time in times),
                    ),
                    (
                        (
                            str(index + 1),
                            *(
                                _safari_slot_cell(
                                    method["base_pools"][time][index], source_file
                                )
                                for time in times
                            ),
                        )
                        for index in range(slot_count)
                    ),
                )
            )
            content.extend([f"{'#' * (heading_level + 2)} Block encounters", ""])
            if not method["block_encounters"]:
                content.extend(["—", ""])
                continue
            content.extend(
                markdown_table_from_cells(
                    (
                        MarkdownColumn("Stored requirements"),
                        *(MarkdownColumn(display_name(time)) for time in times),
                    ),
                    (
                        (
                            ", ".join(
                                f"{requirement['count']} "
                                f"{display_name(requirement['block_type'])}"
                                for requirement in encounter["requirements"]
                            ),
                            *(
                                _safari_slot_cell(encounter["times"][time], source_file)
                                for time in times
                            ),
                        )
                        for encounter in method["block_encounters"]
                    ),
                )
            )
        tabs.append((display_name(version) if version else "Encounter data", content))
    lines.extend(tabs[0][1] if len(tabs) == 1 else content_tabs(tabs))


def conditional_encounter_provenance(record: dict[str, Any]) -> list[str]:
    source_type = record.get("source_type")
    variants = list(version_variant_records(record))
    if source_type == EncounterSourceType.DAILY_SWARM:
        sources = {
            (value["provenance"]["archive"], value["table_offset"])
            for _, value in variants
        }
        return [
            *(
                f"Daily Swarm source: exact ROM table record in `{archive}` at "
                f"offset `0x{offset:X}`."
                for archive, offset in sorted(sources)
            ),
            "The swarm-to-location relationship uses the stored map-header ID.",
        ]
    provenances = {
        (value["provenance"]["archive"], value["provenance"]["member"])
        for _, value in variants
    }
    facts = [
        *(rom_record_source(archive, member) for archive, member in sorted(provenances))
    ]
    if source_type == EncounterSourceType.HEADBUTT:
        facts.extend(
            [
                "The Headbutt member is keyed directly by map-header ID and stores "
                "all three slot pools plus tree-group coordinates.",
                "The trainer ID selects the common or rare regular-tree pool; secret "
                "groups always use the secret pool.",
            ]
        )
    elif source_type == EncounterSourceType.HIDDEN_GROTTO:
        facts.extend(
            [
                "Hidden Grotto Pokémon, levels, gender percentages, forms, and item "
                "IDs come from the Grotto record.",
                "The exterior-map relationship comes from its ROM furniture dispatch ID.",
            ]
        )
    return facts


def conditional_encounter_label(record: dict[str, Any]) -> str:
    source_type = record.get("source_type")
    if source_type == EncounterSourceType.HIDDEN_GROTTO:
        return f"Hidden Grotto {record['grotto_id']:02}"
    if source_type == EncounterSourceType.DAILY_SWARM:
        return "Daily Swarm"
    if source_type == EncounterSourceType.HEADBUTT:
        return "Headbutt encounters"
    return display_name(str(source_type or "encounters"))


def safari_provenance(records: list[dict[str, Any]]) -> list[str]:
    provenances = {
        (value["provenance"]["archive"], value["provenance"]["member"])
        for record in records
        for _, value in version_variant_records(record)
    }
    return [
        *(
            rom_record_source(archive, member)
            for archive, member in sorted(provenances)
        ),
        "Each member stores ten base slots per method and time of day, followed "
        "by block-conditioned records with up to two stored requirements.",
        "Area types can be assigned to different physical Safari Zone positions, "
        "so this page does not invent map-header ownership or replacement priority.",
    ]


def _pokemon_cell(pokemon: dict[str, Any], source_file: str) -> str:
    link = ROUTES.markdown_link(
        entity_reference(
            "pokemon", pokemon["id"], pokemon["name"], pokemon.get("slug")
        ),
        source_file,
    )
    return sprite_with_link(table_sprite_cell(pokemon.get("sprite")), link)


def _type_cell(pokemon: dict[str, Any], references: ReferenceIndex | None) -> str:
    return reference_type_cell("pokemon", pokemon.get("id"), references)


def _safari_slot_cell(slot: dict[str, Any], source_file: str) -> str:
    pokemon = slot["pokemon"]
    link = ROUTES.markdown_link(
        entity_reference("pokemon", pokemon["id"], pokemon["name"], pokemon["slug"]),
        source_file,
    )
    return f"{link} (Lv. {slot['level']})"

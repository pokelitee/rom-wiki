"""Location, same-name, and provenance sections of a trainer page."""

from __future__ import annotations

from html import escape
from typing import Any

from romwiki.renderers.mkdocs.components import MarkdownColumn, markdown_section
from romwiki.renderers.mkdocs.html import (
    html_code,
    html_details,
    html_paragraph,
    html_provenance_fact_table,
    html_provenance_section,
    html_table,
)
from romwiki.renderers.mkdocs.references import (
    ROUTES,
    ReferenceIndex,
    entity_reference,
)
from romwiki.renderers.mkdocs.trainers.records import (
    combined_locations,
    trainer_label,
    trainer_level_range,
    trainer_route_id,
)

_SAME_NAME_COLLAPSE_THRESHOLD = 5

_LOCATION_COLUMNS = (
    MarkdownColumn("Location"),
    MarkdownColumn("Map ID"),
    MarkdownColumn("Internal ID"),
    MarkdownColumn("Position"),
    MarkdownColumn("Event"),
)
_SCRIPT_REFERENCE_COLUMNS = (
    MarkdownColumn("Location"),
    MarkdownColumn("Map ID"),
    MarkdownColumn("Internal ID"),
    MarkdownColumn("Script"),
    MarkdownColumn("Opponent", "right"),
)
_SAME_NAME_COLUMNS = (
    MarkdownColumn("Trainer"),
    MarkdownColumn("ID", "right"),
    MarkdownColumn("Location"),
    MarkdownColumn("Levels", "right"),
    MarkdownColumn("Party"),
)


def _location_link(location: dict[str, Any], source_url: str) -> str:
    return ROUTES.html_link(
        entity_reference(
            "location",
            location["header_id"],
            location["name"],
            location.get("header_id"),
        ),
        source_url,
    )


def locations_section(locations: list[dict[str, Any]], source_url: str) -> list[str]:
    if not locations:
        return []
    rows = [
        (
            _location_link(location, source_url),
            html_code(f"header-{location['header_id']:03}"),
            html_code(location["internal_name"]),
            f"({location['x']}, {location['z']})",
            html_code(f"{location['event_file_id']}:{location['object_index']}"),
        )
        for location in locations
    ]
    return markdown_section("Locations", html_table(_LOCATION_COLUMNS, rows))


def script_references_section(
    references: list[dict[str, Any]], source_url: str
) -> list[str]:
    if not references:
        return []
    rows = [
        (
            _location_link(reference, source_url),
            html_code(f"header-{reference['header_id']:03}"),
            html_code(reference["internal_name"]),
            html_code(
                f"{reference['script_file_id']}@0x{reference['command_offset']:X}"
            ),
            str(reference["opponent_slot"]),
        )
        for reference in references
    ]
    return markdown_section(
        "Scripted battle locations", html_table(_SCRIPT_REFERENCE_COLUMNS, rows)
    )


def same_name_trainers_section(
    record: dict[str, Any],
    same_name_records: list[dict[str, Any]],
    source_url: str,
    references: ReferenceIndex | None = None,
) -> list[str]:
    related = sorted(
        (
            candidate
            for candidate in same_name_records
            if candidate["trainer_id"] != record["trainer_id"]
        ),
        key=lambda candidate: candidate["trainer_id"],
    )
    if not related:
        return []
    rows = []
    for candidate in related:
        trainer_id = candidate["trainer_id"]
        trainer_link = ROUTES.html_link(
            entity_reference(
                "trainer", trainer_id, trainer_label(candidate), trainer_id
            ),
            source_url,
        )
        locations = _location_links(candidate, source_url)
        rows.append(
            (
                trainer_link,
                html_code(trainer_route_id(trainer_id)),
                " / ".join(locations) or "—",
                trainer_level_range(candidate),
                _linked_party(candidate, source_url, references),
            )
        )
    table = html_table(_SAME_NAME_COLUMNS, rows)
    if len(related) > _SAME_NAME_COLLAPSE_THRESHOLD:
        table = html_details(f"{len(related)} other parties", table)
    return markdown_section(
        "Same-name trainers",
        [
            *html_paragraph(
                "These records share the exact trainer class and name. The ROM does "
                "not establish that they represent the same character."
            ),
            *table,
        ],
    )


def _linked_party(
    record: dict[str, Any],
    source_url: str,
    references: ReferenceIndex | None = None,
) -> str:
    links = []
    for member in record["party"]:
        pokemon = member["pokemon"]
        identifier = pokemon.get("id", pokemon.get("slug", pokemon["name"]))
        name = pokemon["name"]
        reference = (
            references.resolve_matching("pokemon", identifier, name)
            if references is not None
            else entity_reference(
                "pokemon",
                identifier,
                name,
                pokemon.get("page_slug", pokemon.get("slug")),
            )
        )
        links.append(ROUTES.html_link(reference, source_url))
    return ", ".join(links)


def _location_links(record: dict[str, Any], source_url: str) -> list[str]:
    links = []
    seen = set()
    for location in combined_locations(record):
        header_id = location.get("header_id")
        identity = (header_id, location["name"])
        if identity in seen:
            continue
        seen.add(identity)
        if not isinstance(header_id, int):
            links.append(escape(location["name"]))
            continue
        links.append(
            ROUTES.html_link(
                entity_reference("location", header_id, location["name"], header_id),
                source_url,
            )
        )
    return links


def provenance(record: dict[str, Any]) -> list[str]:
    return html_provenance_section(_provenance_body(record))


def _provenance_body(record: dict[str, Any]) -> list[str]:
    facts = [("Class ID", html_code(record["class_id"]))]
    if "class_gender" in record:
        facts.append(("Class gender", escape(record["class_gender"].capitalize())))
    facts.append(("AI flags", html_code(f"0x{record['ai_flags']:08X}")))
    if "battle_type" in record:
        facts.append(("Battle type", html_code(record["battle_type"])))
    else:
        facts.append(("Battle mode", html_code(record["battle_mode"])))
    if "unknown_byte" in record:
        facts.append(("Unknown byte", html_code(f"0x{record['unknown_byte']:02X}")))
    if record.get("victory_money_multiplier") is not None:
        facts.append(
            ("Victory money multiplier", html_code(record["victory_money_multiplier"]))
        )
    base_prize_money = record.get("base_prize_money")
    if base_prize_money:
        facts.extend(
            [
                (
                    "Prize-money final party level",
                    html_code(base_prize_money["final_party_level"]),
                ),
                ("Prize-money base factor", html_code(base_prize_money["base_factor"])),
                (
                    "Prize-money battle-format factor",
                    html_code(base_prize_money["battle_format_multiplier"]),
                ),
            ]
        )
    provenance_source = record["provenance"]
    party_source = record["party_provenance"]
    sentences = [
        "Source: exact ROM trainer record from "
        f"{html_code(provenance_source['archive'])} member "
        f"{html_code(provenance_source['member'])} and party record from "
        f"{html_code(party_source['archive'])} member "
        f"{html_code(party_source['member'])}."
    ]
    if base_prize_money:
        multiplier_source = base_prize_money.get("multiplier_provenance") or {}
        if "overlay_id" in multiplier_source:
            offset = html_code(f"0x{multiplier_source['offset']:X}")
            sentences.append(
                "Prize-money multiplier source: ARM9 overlay "
                f"{html_code(multiplier_source['overlay_id'])} at byte offset "
                f"{offset} for trainer class "
                f"{html_code(multiplier_source['class_id'])}."
            )
        elif multiplier_source.get("archive"):
            offset = html_code(f"0x{multiplier_source['offset']:X}")
            sentences.append(
                "Prize-money multiplier source: trainer record byte "
                f"{offset} in "
                f"{html_code(multiplier_source['archive'])} member "
                f"{html_code(multiplier_source['member'])}."
            )
    if record.get("locations"):
        sentences.append(
            "Overworld locations: trainer event objects whose script IDs "
            "resolve directly to this trainer record."
        )
    if record.get("script_references"):
        sentences.append(
            "Scripted battle locations: literal "
            f"{html_code('StartTrainerBattle')} commands followed by "
            f"{html_code('CheckWonBattle')}; only literal trainer IDs are linked."
        )
    return [
        *html_provenance_fact_table(facts),
        "<p>" + "\n".join(sentences) + "</p>",
    ]

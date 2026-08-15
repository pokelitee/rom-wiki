from __future__ import annotations

from typing import Any, Required, TypedDict


class RenderReference(TypedDict, total=False):
    source: str
    source_url: str
    name: str
    short_effect: str
    effect: str
    flavor_text: str
    flavor_text_label: str
    flavor_text_source: str
    version: str
    metadata: dict[str, Any]


class RenderProvenance(TypedDict, total=False):
    archive: Required[str]
    member: Required[int | str]
    offset: int
    record_size: int
    source: str


class VersionedRenderRecord(TypedDict, total=False):
    versions: list[str]
    version_variants: dict[str, dict[str, Any]]
    reference_variants: dict[str, RenderReference | None]
    reference: RenderReference
    provenance: RenderProvenance


class PokemonRenderRecord(VersionedRenderRecord, total=False):
    id: Required[int]
    name: Required[str]
    slug: Required[str]


class AbilityRenderRecord(VersionedRenderRecord, total=False):
    id: Required[int]
    name: Required[str]
    slug: Required[str]


class ItemRenderRecord(VersionedRenderRecord, total=False):
    id: Required[int]
    name: Required[str]
    slug: Required[str]


class MoveRenderRecord(VersionedRenderRecord, total=False):
    id: Required[int]
    name: Required[str]
    slug: Required[str]


class TrainerRenderRecord(VersionedRenderRecord, total=False):
    trainer_id: Required[int]
    name: Required[str]


class EncounterRenderRecord(VersionedRenderRecord, total=False):
    index: Required[int]
    name: Required[str]


class LocationRenderRecord(VersionedRenderRecord, total=False):
    header_id: Required[int]
    name: Required[str]
    section_name: str | None


class RenderDataset[RecordT: VersionedRenderRecord](TypedDict, total=False):
    schema_version: Required[int]
    game: Required[str]
    engine: Required[str]
    dataset: Required[str]
    record_count: Required[int]
    source: Required[dict[str, Any]]
    records: Required[list[RecordT]]
    name_source: dict[str, Any] | None
    description_source: dict[str, Any] | None
    description_sources: dict[str, dict[str, Any]]

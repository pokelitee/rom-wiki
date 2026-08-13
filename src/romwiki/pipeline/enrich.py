"""Compatibility imports for the dataset-specific enrichment modules."""

from romwiki.pipeline.encounter_enrichment import enrich_encounter_dataset
from romwiki.pipeline.move_enrichment import enrich_move_dataset
from romwiki.pipeline.pokemon_enrichment import (
    enrich_personal_dataset,
    write_enriched_dataset,
)
from romwiki.pipeline.trainer_enrichment import (
    enrich_trainer_dataset,
    enrich_trainer_record,
)

_enrich_trainer = enrich_trainer_record

__all__ = [
    "enrich_encounter_dataset",
    "enrich_move_dataset",
    "enrich_personal_dataset",
    "enrich_trainer_dataset",
    "write_enriched_dataset",
]

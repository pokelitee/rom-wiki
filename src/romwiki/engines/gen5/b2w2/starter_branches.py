from __future__ import annotations

from collections.abc import Sequence

from romwiki.engines.gen5.shared.starter_branches import (
    Gen5StarterBranchFamily,
)
from romwiki.engines.gen5.shared.starter_branches import (
    parse_starter_branch_families as _parse_starter_branch_families,
)

from .opcode_table import OPCODE_TABLE


def parse_starter_branch_families(
    data: bytes,
    *,
    script_file_id: int,
    trainer_count: int,
    starter_species: Sequence[int] | None = None,
) -> tuple[Gen5StarterBranchFamily, ...]:
    """Decode a B2W2 script's starter-selected battles with the sequel's opcodes."""
    return _parse_starter_branch_families(
        data,
        script_file_id=script_file_id,
        trainer_count=trainer_count,
        starter_species=starter_species,
        opcode_table=OPCODE_TABLE,
    )

from __future__ import annotations

import struct
from dataclasses import dataclass

from romwiki.util.errors import InvalidRomError

REMATCH_RECORD_SIZE = 12
REMATCH_STAGE_COUNT = 5

# A stage slot the base trainer never upgrades in. Trainers first battled late
# in the story carry these in their early slots, so the slot index is a
# story-progress tier rather than a plain sequence position.
NO_STAGE_RECORD = 0xFFFF

# Trailing padding. Every record's zeros form a suffix run, so a zero also
# terminates the chain.
UNUSED_STAGE = 0x0000


@dataclass(frozen=True, slots=True)
class Gen4RematchChain:
    """One Vs. Seeker rematch chain, keyed by the trainer that starts it."""

    base_trainer_id: int
    #: (stage slot, trainer ID) for each slot holding a distinct record.
    stages: tuple[tuple[int, int], ...]

    @property
    def trainer_ids(self) -> tuple[int, ...]:
        return (self.base_trainer_id, *(trainer_id for _, trainer_id in self.stages))

    @property
    def has_distinct_records(self) -> bool:
        """Whether the chain selects any record other than its base.

        Most entries re-select the base trainer, which means "rematchable with
        an unchanged party" and carries no variant information.
        """
        return any(trainer_id != self.base_trainer_id for _, trainer_id in self.stages)


def parse_rematch_table(
    data: bytes, *, count: int, trainer_count: int
) -> tuple[Gen4RematchChain, ...]:
    """Decode the DPPT Vs. Seeker rematch table.

    Each 12-byte record is a base trainer ID followed by five stage slots. The
    table is validated against the invariants that hold for the retail layout:
    base IDs are unique and in range, every stage record is referenced exactly
    once across the whole table, and unused slots only ever form a trailing run.
    A ROM that violates them is not this table, so decoding fails rather than
    inventing relationships.
    """
    expected = count * REMATCH_RECORD_SIZE
    if len(data) != expected:
        raise InvalidRomError(
            f"Gen IV rematch table has size {len(data)}; expected {expected}"
        )

    chains: list[Gen4RematchChain] = []
    seen_bases: set[int] = set()
    seen_stages: set[int] = set()
    for index in range(count):
        values = struct.unpack_from("<6H", data, index * REMATCH_RECORD_SIZE)
        base_trainer_id, slots = values[0], values[1:]
        if not 0 < base_trainer_id < trainer_count:
            raise InvalidRomError(
                f"Gen IV rematch record {index} has invalid base trainer "
                f"{base_trainer_id}"
            )
        if base_trainer_id in seen_bases:
            raise InvalidRomError(
                f"Gen IV rematch record {index} repeats base trainer {base_trainer_id}"
            )
        seen_bases.add(base_trainer_id)

        stages: list[tuple[int, int]] = []
        terminated = False
        for slot, trainer_id in enumerate(slots, start=1):
            if trainer_id == UNUSED_STAGE:
                terminated = True
                continue
            if terminated:
                raise InvalidRomError(
                    f"Gen IV rematch record {index} has a stage after its terminator"
                )
            if trainer_id == NO_STAGE_RECORD:
                continue
            if not 0 < trainer_id < trainer_count:
                raise InvalidRomError(
                    f"Gen IV rematch record {index} slot {slot} has invalid trainer "
                    f"{trainer_id}"
                )
            # The base re-selecting itself is the "unchanged party" encoding and
            # is the one legitimate repeat.
            if trainer_id != base_trainer_id:
                if trainer_id in seen_stages:
                    raise InvalidRomError(
                        f"Gen IV rematch record {index} reuses stage trainer "
                        f"{trainer_id}"
                    )
                seen_stages.add(trainer_id)
            stages.append((slot, trainer_id))

        chains.append(
            Gen4RematchChain(base_trainer_id=base_trainer_id, stages=tuple(stages))
        )
    return tuple(chains)

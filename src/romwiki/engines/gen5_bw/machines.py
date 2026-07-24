from __future__ import annotations

from romwiki.engines.gen5_bw.constants import GEN5_MACHINE_COUNT, GEN5_TM_COUNT


def machine_name(machine_id: int) -> str:
    """Format a machine ID the way `PersonalInfo5BW`'s TM/HM bitmap would."""
    if machine_id <= GEN5_TM_COUNT:
        return f"TM{machine_id:02}"
    if machine_id <= GEN5_MACHINE_COUNT:
        return f"HM{machine_id - GEN5_TM_COUNT:02}"
    return f"MACHINE{machine_id:03}"

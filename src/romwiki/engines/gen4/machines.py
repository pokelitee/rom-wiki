GEN4_MACHINE_COUNT = 100
GEN4_TM_COUNT = 92


def machine_name(machine_id: int) -> str:
    if machine_id <= GEN4_TM_COUNT:
        return f"TM{machine_id:02}"
    if machine_id <= GEN4_MACHINE_COUNT:
        return f"HM{machine_id - GEN4_TM_COUNT:02}"
    return f"MACHINE{machine_id:03}"

